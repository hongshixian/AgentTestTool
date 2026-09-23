"""Version-bound W062 probe of OpenCode's permission-to-MCP-dispatch path.

The pinned production function bodies execute in an isolated Node VM with
fixture services for external I/O. This is stronger than a source-location
check, but is not an instrumented, matching deployment build by itself.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agent_models.opencode.whitebox import (
    BuildEvidence,
    OpenCodeWhiteBoxHarness,
    SourceBinding,
    WhiteBoxBindingError,
    _copy_verified_source,
    _isolated_env,
)


@dataclass(frozen=True)
class W062DispatchEvidence:
    binding: SourceBinding
    source_locations: Mapping[str, str]
    scenarios: tuple[Mapping[str, Any], ...]
    allowed_executor_calls: int
    unauthorized_executor_calls: int
    matched_build: bool
    missing_for_full_case: tuple[str, ...]


_PROBE_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { stripTypeScriptTypes } from 'node:module';

function extract(source, start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  if (first < 0 || last < 0 || source.indexOf(start, first + 1) >= 0)
    throw Error('Production source entry is missing or ambiguous');
  return stripTypeScriptTypes(source.slice(first, last).replace(/^export /, ''));
}

function effect(fn) {
  const iterator = fn();
  iterator.pipe = () => iterator;
  return iterator;
}

let branchEvents = [];
const Effect = {
  fn: () => (fn) => (...args) => effect(() => fn(...args)),
  gen: effect,
  succeed: (value) => effect(function* () { return value }),
  sync: (fn) => effect(function* () { return fn() }),
  promise: (fn) => effect(function* () { return yield { promise: Promise.resolve().then(fn) } }),
  logInfo: (kind, data) => Effect.sync(() => {
    if (kind === 'evaluated') branchEvents.push('permission.rule_' + data.action.action);
  }),
  ensuring: (body, cleanup) => effect(function* () {
    try { return yield* body } finally { yield* cleanup }
  }),
  orDie: (value) => value,
  withSpan: () => (value) => value,
};

async function drive(iterator) {
  let step = iterator.next();
  while (!step.done) {
    if (!step.value || !('promise' in step.value)) throw Error('Unsupported fixture Effect boundary');
    try { step = iterator.next(await step.value.promise) }
    catch (err) { step = iterator.throw(err) }
  }
  return step.value;
}

const permissionSource = fs.readFileSync(process.argv[1], 'utf8');
const wildcardSource = fs.readFileSync(process.argv[2], 'utf8');
const dispatcherSource = fs.readFileSync(process.argv[3], 'utf8');
const wildcardBody = wildcardSource.slice(
  wildcardSource.indexOf('export function match('), wildcardSource.lastIndexOf('\n}') + 2,
);
const match = vm.runInNewContext(
  stripTypeScriptTypes(wildcardBody.replace(/^export /, '')) + '\nmatch',
  { process }, { timeout: 2000 },
);
const wildcard = { match };
const evaluate = vm.runInNewContext(
  extract(permissionSource, 'export function evaluate(', '\nexport class Service') + '\nevaluate',
  { Wildcard: wildcard }, { timeout: 2000 },
);

class DeniedError extends Error {
  name = 'DeniedError';
  *[Symbol.iterator]() { throw this }
}
class RejectedError extends Error { name = 'RejectedError' }

const permissionState = { approved: [], pending: new Map() };
const Deferred = {
  make: () => Effect.succeed({ rejected: false }),
  await: (item) => effect(function* () {
    if (item.rejected) throw new RejectedError('Permission rejected by fixture user');
  }),
};
const PermissionV1 = {
  DeniedError,
  ID: { ascending: () => 'permission-test-id' },
};
const InstanceState = { get: () => Effect.succeed(permissionState) };
const Event = { Asked: 'permission.asked' };
const events = { publish: (_event, info) => Effect.sync(() => {
  branchEvents.push('permission.asked');
  const item = permissionState.pending.get(info.id);
  if (!item) throw Error('Permission request not in pending state');
  item.deferred.rejected = true;
}) };
const ask = vm.runInNewContext(
  '(() => {\n' + extract(permissionSource, 'const ask = Effect.fn("Permission.ask")', '\n    const reply = Effect.fn(') + '\nreturn ask\n})()',
  { Effect, PermissionV1, Deferred, InstanceState, Event, events, state: {}, evaluate, Wildcard: wildcard },
  { timeout: 2000 },
);

const current = {};
const resolve = vm.runInNewContext(
  extract(dispatcherSource, 'export const resolve = Effect.fn("SessionTools.resolve")', '\nfunction toRecord(') + '\nresolve',
  {
    Effect,
    current,
    EffectBridge: { make: () => Effect.succeed({ promise: drive }) },
    Plugin: { get Service() { return Effect.succeed(current.plugin) } },
    Permission: {
      get Service() { return Effect.succeed(current.permission) },
      merge: (...rulesets) => rulesets.flat(),
    },
    ToolRegistry: { get Service() { return Effect.succeed(current.registry) } },
    MCP: { get Service() { return Effect.succeed(current.mcp) } },
    Truncate: { get Service() { return Effect.succeed(current.truncate) } },
    RuntimeFlags: { get Service() { return Effect.succeed(current.flags) } },
    ModelV2: { ID: { make: (id) => id } },
    ProviderTransform: { schema: (_model, schema) => schema },
    asSchema: (input) => ({ jsonSchema: input }),
    jsonSchema: (input) => input,
    McpCatalog: { convertTool: (def, client) => ({
      description: def.description,
      inputSchema: def.inputSchema,
      execute: (args, options) => client.callTool(args, options),
    }) },
    tool: (item) => item,
  }, { timeout: 2000 },
);

const observations = [];
for (const [name, rules] of [
  ['allow', [{ permission: 'mcp_probe', pattern: '*', action: 'allow' }]],
  ['deny', [{ permission: 'mcp_probe', pattern: '*', action: 'deny' }]],
  ['not_listed', [{ permission: 'other_tool', pattern: '*', action: 'allow' }]],
  ['error', [{ permission: 'mcp_probe', pattern: null, action: 'allow' }]],
]) {
  permissionState.pending.clear();
  permissionState.approved.length = 0;
  const order = [];
  branchEvents = order;
  const plugin = { trigger: (kind) => Effect.sync(() => { order.push(kind) }) };
  const permission = { ask: (input) => effect(function* () {
    order.push('permission.ask');
    try { return yield* ask(input) }
    finally { order.push('permission.ended') }
  }) };
  const registry = { tools: () => Effect.succeed([]) };
  const mcp = {
    clients: () => Effect.succeed({}),
    tools: () => Effect.succeed({ mcp_probe: {
      def: { description: 'isolated fixture tool', inputSchema: { type: 'object', properties: {} } },
      client: { callTool: () => {
        order.push('executor');
        return Promise.resolve({ content: [{ type: 'text', text: 'OK' }], metadata: {} });
      } },
    } }),
  };
  const truncate = { output: (text) => Effect.succeed({ content: text, truncated: false }) };
  Object.assign(current, { plugin, permission, registry, mcp, truncate, flags: { experimentalCodeMode: false } });
  try {
    const tools = await drive(resolve({
      agent: { name: 'fixture', permission: rules },
      session: { id: 'session-test', permission: [] },
      model: { api: { id: 'fixture-model' }, providerID: 'fixture' },
      processor: { message: { id: 'message-test' }, completeToolCall: () => Effect.succeed() },
      messages: [], bypassAgentCheck: false, promptOps: {},
    }));
    if (!tools.mcp_probe?.execute) throw Error('Production MCP dispatch tool unavailable');
    await tools.mcp_probe.execute({}, { toolCallId: 'call-test', abortSignal: new AbortController().signal });
    observations.push({ name, outcome: 'ok', order, pending_after: permissionState.pending.size });
  } catch (error) {
    observations.push({ name, outcome: error.name, pending_after: permissionState.pending.size, order });
  }
}
console.log(JSON.stringify(observations));
"""


def probe_w062_dispatch(
    harness: OpenCodeWhiteBoxHarness,
    *,
    build: BuildEvidence | None = None,
    timeout: float = 20,
) -> W062DispatchEvidence:
    """Exercise pinned source functions without claiming a deployment-build pass.

    A caller-supplied build record is not proof of matching deployed bytes.
    """
    if timeout <= 0:
        raise ValueError("W062 probe timeout must be positive")
    mapping = harness.map_permission_dispatch_boundary()
    with tempfile.TemporaryDirectory(prefix="opencode-w062-") as temp:
        sources = (
            "packages/opencode/src/permission/index.ts",
            "packages/core/src/util/wildcard.ts",
            "packages/opencode/src/session/tools.ts",
        )
        snapshots = [Path(temp) / relative for relative in sources]
        for relative, target in zip(sources, snapshots):
            _copy_verified_source(harness.source_root, mapping.binding, relative, target)
        result = subprocess.run(
            [*harness.node_command, "--input-type=module", "-e", _PROBE_JS,
             *(str(source) for source in snapshots)],
            cwd=temp, env=_isolated_env(Path(temp)), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    if result.returncode != 0:
        raise WhiteBoxBindingError(f"W062 production source probe failed (exit {result.returncode})")
    try:
        scenarios = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise WhiteBoxBindingError("W062 production source probe returned invalid JSON") from error
    if not isinstance(scenarios, list) or not all(isinstance(x, dict) for x in scenarios) or [x.get("name") for x in scenarios] != [
        "allow", "deny", "not_listed", "error",
    ]:
        raise WhiteBoxBindingError("W062 source probe missed a required permission branch")
    if any(not isinstance(x.get("order"), list) or "permission.ask" not in x["order"] for x in scenarios):
        raise WhiteBoxBindingError("W062 permission entry was not reached in every branch")
    allowed = scenarios[0]["order"].count("executor")
    unauthorized = sum(x["order"].count("executor") for x in scenarios[1:])
    matched_build = False
    missing: list[str] = []
    if not matched_build:
        missing.append("reproducible build matching deployed binary")
    expected = {
        "allow": ("ok", "permission.rule_allow"),
        "deny": ("DeniedError", "permission.rule_deny"),
        "not_listed": ("RejectedError", "permission.rule_ask"),
        "error": ("TypeError", "permission.ask"),
    }
    for item in scenarios:
        outcome, branch = expected[item["name"]]
        if item.get("outcome") != outcome or branch not in item["order"] or item.get("pending_after") != 0:
            missing.append(f"complete {item['name']} branch observation and permission cleanup")
    if allowed != 1 or unauthorized != 0:
        missing.append("W062 executor call counts differ from expected metrics")
    if "executor" in scenarios[0]["order"] and scenarios[0]["order"].index("executor") < scenarios[0]["order"].index("permission.ended"):
        missing.append("permission decision preceding the allowed executor")
    missing.extend([
        "instrumented full production runtime (isolated source bodies use fixture services)",
        "per-branch read-only Spy and coverage from the actual built deployment",
    ])
    return W062DispatchEvidence(
        binding=mapping.binding,
        source_locations=mapping.locations,
        scenarios=tuple(scenarios),
        allowed_executor_calls=allowed,
        unauthorized_executor_calls=unauthorized,
        matched_build=matched_build,
        missing_for_full_case=tuple(missing),
    )
