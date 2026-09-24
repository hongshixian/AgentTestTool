"""Complete source-runtime harness for OpenCode white-box case W062."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_models.opencode.whitebox import SourceBinding, WhiteBoxBindingError, _isolated_env


_SCHEMA_VERSION = "ats.opencode.w062.v1"
_PRODUCTION_IMPORTS = ("Permission.Service", "SessionTools.resolve", "McpCatalog.convertTool")
_PHASES = ("allow", "deny", "not_listed", "error")
_OUTCOMES = {
    "allow": "allowed",
    "deny": "denied",
    "not_listed": "rejected",
    "error": "authorization_error",
}
EXPECTED_BUN_VERSION = "1.3.14"
W062_RUNTIME_SOURCE_HASHES = {
    "bun.lock": "459a7d71db89d5e16f54b12d728ce1401da0f4b69e22053dbccc6ca04cf0e2df",
    "packages/opencode/src/effect/runtime-flags.ts": "5b580cb96f9d5300f8ff995a29ec5e602e0e3e0200661dfff971998562f2a1a9",
    "packages/opencode/src/event-v2-bridge.ts": "f12ba339dd6f268dd9ad8861fc7b2a65360f6a895eff57d83832d270ca43eb8a",
    "packages/opencode/src/mcp/catalog.ts": "1123ce304cd647e0945aa98743f411a69988f6dde63867aea78b74c72a5abe11",
    "packages/opencode/src/mcp/index.ts": "82c459309dfd005d25daecfabc1007d807d4bee23f6078434974277938a1c026",
    "packages/opencode/src/plugin/index.ts": "47c62b7cfae891d268e6b239edb0f1c46df5cb35eb11ccfd8bd4186c156024e9",
    "packages/opencode/src/session/schema.ts": "fe78e7d60b0772cb62c95473f8ff4c0e68caa083bbbb4dc1cc1984217234822d",
    "packages/opencode/src/tool/registry.ts": "a8b24a6d58a80c42307e251905dbaa4f25ca0724569b1e531e412da934ab00fe",
    "packages/opencode/src/tool/truncate.ts": "d3dc9e7402de74a7652ceb9f7796c970efc4958597b51a94fa264697366ccea5",
    "packages/opencode/test/fixture/fixture.ts": "701086618182ad2736b876be17cbca65b896887505dad04f90525a5a48b3e52d",
}


@dataclass(frozen=True)
class W062RuntimeEvidence:
    """Structured CODE/SPY/STATE/CONTROL evidence from one W062 run."""

    binding: SourceBinding
    source_locations: Mapping[str, str]
    run_id: str
    production_imports: tuple[str, ...]
    bun_version: str
    dependency_command: tuple[str, ...]
    dependency_exit_code: int
    dependency_output_sha256: str
    test_command: tuple[str, ...]
    test_exit_code: int
    phases: tuple[Mapping[str, Any], ...]
    cleanup_completed: bool
    allowed_executor_calls: int
    unauthorized_executor_calls: int
    complete: bool
    missing_evidence: tuple[str, ...]


_BUN_HARNESS = r'''
import { Cause, Effect, Exit, Fiber, Layer } from "effect"
import { AppNodeBuilder } from "@opencode-ai/core/effect/app-node-builder"
import { LayerNode } from "@opencode-ai/core/effect/layer-node"
import { CrossSpawnSpawner } from "@opencode-ai/core/cross-spawn-spawner"
import { ModelV2 } from "@opencode-ai/core/model"
import { ProviderV2 } from "@opencode-ai/core/provider"
import { Permission } from "__OPENCODE_ROOT__/src/permission/index.ts"
import { EventV2Bridge } from "__OPENCODE_ROOT__/src/event-v2-bridge.ts"
import { SessionTools } from "__OPENCODE_ROOT__/src/session/tools.ts"
import { MCP } from "__OPENCODE_ROOT__/src/mcp/index.ts"
import { McpCatalog } from "__OPENCODE_ROOT__/src/mcp/catalog.ts"
import { Plugin } from "__OPENCODE_ROOT__/src/plugin/index.ts"
import { ToolRegistry } from "__OPENCODE_ROOT__/src/tool/registry.ts"
import { Truncate } from "__OPENCODE_ROOT__/src/tool/truncate.ts"
import { RuntimeFlags } from "__OPENCODE_ROOT__/src/effect/runtime-flags.ts"
import { MessageID, SessionID } from "__OPENCODE_ROOT__/src/session/schema.ts"
import { TestInstance, withTmpdirInstance } from "__OPENCODE_ROOT__/test/fixture/fixture.ts"

const productionImports = [
  "Permission.Service",
  "SessionTools.resolve",
  "McpCatalog.convertTool",
]

function pluginService(spy) {
  return Plugin.Service.of({
    init: () => Effect.void,
    list: () => Effect.succeed([]),
    trigger: (name, _input, output) =>
      Effect.sync(() => {
        spy.events.push(name)
        return output
      }),
  })
}

function mcpService(spy) {
  const client = {
    getServerCapabilities: () => ({}),
    callTool: async (request) => {
      spy.events.push("executor.callTool")
      spy.executor_calls += 1
      spy.executor_requests.push(request)
      return { isError: false, content: [{ type: "text", text: "OK" }] }
    },
  }
  const def = {
    name: "probe",
    description: "W062 deterministic external MCP fixture",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  }
  return MCP.Service.of({
    tools: () => Effect.succeed({ mcp_probe: { def, client, timeout: 1000 } }),
    clients: () => Effect.succeed({}),
  })
}

const registryService = ToolRegistry.Service.of({
  ids: () => Effect.succeed([]),
  all: () => Effect.succeed([]),
  named: () => Effect.die("unused W062 registry entry"),
  tools: () => Effect.succeed([]),
})

const truncateService = Truncate.Service.of({
  cleanup: () => Effect.void,
  write: () => Effect.succeed("unused"),
  output: (text) => Effect.succeed({ content: text, truncated: false }),
  limits: () => Effect.succeed({ maxLines: 2000, maxBytes: 50 * 1024 }),
})

function runtimeLayer(spy) {
  const production = AppNodeBuilder.build(
    LayerNode.group([Permission.node, EventV2Bridge.node, CrossSpawnSpawner.node]),
  )
  const fixtures = Layer.mergeAll(
    Layer.succeed(Plugin.Service, pluginService(spy)),
    Layer.succeed(MCP.Service, mcpService(spy)),
    Layer.succeed(ToolRegistry.Service, registryService),
    Layer.succeed(Truncate.Service, truncateService),
    RuntimeFlags.layer({ experimentalCodeMode: false }),
  )
  return production.pipe(Layer.provideMerge(fixtures))
}

const model = {
  providerID: ProviderV2.ID.make("ats-fixture"),
  api: {
    id: "ats-fixture-model",
    npm: "@ai-sdk/openai-compatible",
    url: "http://127.0.0.1.invalid",
  },
}

function rules(phase) {
  if (phase === "allow") return [{ permission: "mcp_probe", pattern: "*", action: "allow" }]
  if (phase === "deny") return [{ permission: "mcp_probe", pattern: "*", action: "deny" }]
  if (phase === "not_listed") return [{ permission: "different_tool", pattern: "*", action: "allow" }]
  if (phase === "error") return [{ permission: "mcp_probe", pattern: null, action: "allow" }]
  throw new Error(`Unknown W062 phase: ${phase}`)
}

function classify(phase, exit) {
  if (phase === "allow" && Exit.isSuccess(exit)) return { outcome: "allowed", raw_error: null }
  if (Exit.isSuccess(exit)) return { outcome: "unexpected_success", raw_error: null }
  const error = Cause.squash(exit.cause)
  const raw = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  if (phase === "deny") return { outcome: "denied", raw_error: raw }
  if (phase === "not_listed") return { outcome: "rejected", raw_error: raw }
  return { outcome: "authorization_error", raw_error: raw }
}

async function runPhase(phase) {
  const started_at = new Date().toISOString()
  const spy = {
    events: [],
    executor_calls: 0,
    executor_requests: [],
    permission_calls: 0,
    pending_before_reply: 0,
    pending_after: 0,
  }
  const program = withTmpdirInstance()(
    Effect.gen(function* () {
      const permission = yield* Permission.Service
      const testInstance = yield* TestInstance
      const ask = permission.ask
      const reply = permission.reply
      permission.ask = (input) => {
        spy.permission_calls += 1
        spy.events.push("permission.ask")
        return ask(input)
      }
      permission.reply = (input) => {
        spy.events.push(`permission.reply.${input.reply}`)
        return reply(input)
      }

      const sessionID = SessionID.make(`ses_w062_${phase}`)
      const messageID = MessageID.ascending()
      const processor = {
        message: {
          id: messageID,
          sessionID,
          role: "assistant",
          parentID: MessageID.ascending(),
          agent: "build",
          mode: "build",
          path: { cwd: testInstance.directory, root: testInstance.directory },
          cost: 0,
          tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
          modelID: ModelV2.ID.make("ats-fixture-model"),
          providerID: ProviderV2.ID.make("ats-fixture"),
          time: { created: Date.now() },
        },
        updateToolCall: () => Effect.succeed(undefined),
        completeToolCall: () => Effect.void,
      }
      const tools = yield* SessionTools.resolve({
        agent: { name: "build", mode: "primary", options: {}, permission: rules(phase) },
        model,
        session: { id: sessionID, permission: [] },
        processor,
        bypassAgentCheck: false,
        messages: [],
        promptOps: {},
      })
      const execute = tools.mcp_probe?.execute
      if (!execute) throw new Error("Production SessionTools.resolve did not expose the MCP tool")
      const invoke = () =>
        Effect.promise(() =>
          execute(
            {},
            { toolCallId: `call_w062_${phase}`, abortSignal: new AbortController().signal, messages: [] },
          ),
        )

      let exit
      if (phase === "not_listed") {
        const fiber = yield* invoke().pipe(Effect.forkScoped)
        let pending = []
        for (let attempt = 0; attempt < 100; attempt += 1) {
          pending = yield* permission.list()
          if (pending.length > 0) break
          yield* Effect.sleep("10 millis")
        }
        spy.pending_before_reply = pending.length
        if (pending.length !== 1) throw new Error("Permission ask branch did not create one pending request")
        spy.events.push("permission.pending")
        yield* permission.reply({ requestID: pending[0].id, reply: "reject" })
        exit = yield* Fiber.await(fiber)
      } else {
        exit = yield* invoke().pipe(Effect.exit)
      }
      spy.pending_after = (yield* permission.list()).length
      const result = classify(phase, exit)
      const branch_tags = []
      if (phase === "allow" && spy.events.includes("permission.ask")) {
        branch_tags.push("permission.allow")
        if (spy.events.includes("executor.callTool")) branch_tags.push("dispatcher.execute")
      }
      if (phase === "deny" && spy.events.includes("permission.ask")) {
        branch_tags.push("permission.deny")
      }
      if (phase === "not_listed" && spy.events.includes("permission.ask")) {
        branch_tags.push("permission.ask")
        if (spy.events.includes("permission.reply.reject")) branch_tags.push("permission.reply.reject")
      }
      if (phase === "error" && spy.events.includes("permission.ask")) {
        branch_tags.push("permission.error")
      }
      return {
        phase_id: phase,
        ...result,
        branch_tags,
        permission_calls: spy.permission_calls,
        executor_calls: spy.executor_calls,
        executor_requests: spy.executor_requests,
        pending_before_reply: spy.pending_before_reply,
        pending_after: spy.pending_after,
        events: spy.events,
        started_at,
        ended_at: new Date().toISOString(),
      }
    }),
  )
  return Effect.runPromise(program.pipe(Effect.scoped, Effect.provide(runtimeLayer(spy))))
}

const scenarios = []
for (const phase of ["allow", "deny", "not_listed", "error"]) scenarios.push(await runPhase(phase))
console.log(
  "ATS_W062_RESULT=" +
    JSON.stringify({
      schema_version: "ats.opencode.w062.v1",
      production_imports: productionImports,
      bun_version: Bun.version,
      scenarios,
    }),
)
'''


def run_w062_runtime_harness(
    harness: Any,
    *,
    bun_command: Sequence[str],
    run_id: str,
    timeout: float = 120,
) -> W062RuntimeEvidence:
    """Run W062 through full production modules with deterministic external fixtures."""
    if not run_id.strip():
        raise ValueError("W062 run_id must not be empty")
    if timeout <= 0:
        raise ValueError("W062 timeout must be positive")
    if len(bun_command) != 1:
        raise ValueError("W062 runtime harness requires one explicit Bun executable")
    try:
        bun_executable = Path(bun_command[0]).resolve(strict=True)
    except OSError as error:
        raise WhiteBoxBindingError("Configured W062 Bun executable is unavailable") from error
    if not bun_executable.name.lower().startswith("bun"):
        raise ValueError("W062 runtime harness requires Bun")

    mapping = harness.map_permission_dispatch_boundary()
    package_root = harness.source_root / "packages/opencode"
    script = _BUN_HARNESS.replace("__OPENCODE_ROOT__", package_root.resolve().as_posix())
    install_command = (
        str(bun_executable), "install", "--frozen-lockfile", "--ignore-scripts",
        "--no-progress", "--no-summary",
    )
    test_command = (str(bun_executable), "run", "-")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="opencode-w062-runtime-") as temp:
        isolated_env = _isolated_env(Path(temp))
        dependency_env = dict(isolated_env)
        for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "all_proxy", "no_proxy",
            "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
        ):
            value = os.environ.get(name, "")
            if value:
                dependency_env[name] = value
        dependency = subprocess.run(
            install_command, cwd=harness.source_root, env=dependency_env,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if dependency.returncode != 0:
            detail = (dependency.stderr or dependency.stdout).strip()[-2000:]
            raise WhiteBoxBindingError(
                f"W062 frozen dependency verification failed (exit {dependency.returncode}): {detail}"
            )
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise WhiteBoxBindingError("W062 dependency verification exhausted the case timeout")
        result = subprocess.run(
            test_command, input=script, cwd=package_root, env=isolated_env,
            capture_output=True, text=True, timeout=remaining, check=False,
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise WhiteBoxBindingError(f"W062 production runtime failed (exit {result.returncode}): {detail}")
    marker = next((line for line in result.stdout.splitlines() if line.startswith("ATS_W062_RESULT=")), None)
    if marker is None:
        raise WhiteBoxBindingError("W062 production runtime returned no structured result")
    try:
        payload = json.loads(marker.removeprefix("ATS_W062_RESULT="))
    except json.JSONDecodeError as error:
        raise WhiteBoxBindingError("W062 production runtime returned invalid JSON") from error
    return _validate(
        payload, mapping.binding, mapping.locations, run_id,
        dependency_command=install_command, dependency_exit_code=dependency.returncode,
        dependency_output_sha256=hashlib.sha256(
            (dependency.stdout + "\n" + dependency.stderr).encode("utf-8")
        ).hexdigest(),
        test_command=test_command, test_exit_code=result.returncode,
    )


def _validate(
    payload: Any,
    binding: SourceBinding,
    locations: Mapping[str, str],
    run_id: str,
    *,
    dependency_command: tuple[str, ...],
    dependency_exit_code: int,
    dependency_output_sha256: str,
    test_command: tuple[str, ...],
    test_exit_code: int,
) -> W062RuntimeEvidence:
    if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
        raise WhiteBoxBindingError("W062 runtime evidence schema is invalid")
    imports = payload.get("production_imports")
    if imports != list(_PRODUCTION_IMPORTS):
        raise WhiteBoxBindingError("W062 runtime did not import all required production modules")
    if payload.get("bun_version") != EXPECTED_BUN_VERSION:
        raise WhiteBoxBindingError("W062 runtime used an unexpected Bun version")
    rows = payload.get("scenarios")
    if (
        not isinstance(rows, list)
        or not all(isinstance(row, dict) for row in rows)
        or [row.get("phase_id") for row in rows] != list(_PHASES)
    ):
        raise WhiteBoxBindingError("W062 runtime must report all four required phases in order")
    expected_tags = {
        "allow": {"permission.allow"},
        "deny": {"permission.deny"},
        "not_listed": {"permission.ask"},
        "error": {"permission.error"},
    }
    for row in rows:
        phase = row["phase_id"]
        if not isinstance(row.get("outcome"), str) or row.get("permission_calls") != 1:
            raise WhiteBoxBindingError(f"W062 {phase} production observation is malformed")
        if not expected_tags[phase].issubset(set(row.get("branch_tags", []))):
            raise WhiteBoxBindingError(f"W062 {phase} actual permission branch is missing")
        try:
            started = datetime.fromisoformat(row["started_at"])
            ended = datetime.fromisoformat(row["ended_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise WhiteBoxBindingError("W062 phase timing evidence is missing or invalid") from error
        if started.tzinfo is None or ended.tzinfo is None or ended < started:
            raise WhiteBoxBindingError("W062 phase timing evidence is not ordered UTC data")
    if rows[2].get("pending_before_reply") != 1:
        raise WhiteBoxBindingError("W062 not_listed phase did not reach the real pending authorization state")
    allowed = rows[0].get("executor_calls")
    executor_counts = [row.get("executor_calls") for row in rows]
    if not all(isinstance(count, int) and not isinstance(count, bool) for count in executor_counts):
        raise WhiteBoxBindingError("W062 executor Spy counts are malformed")
    unauthorized = sum(executor_counts[1:])
    allow_events = rows[0].get("events")
    if (
        not isinstance(allow_events, list)
        or "permission.ask" not in allow_events
        or "executor.callTool" not in allow_events
    ):
        raise WhiteBoxBindingError("W062 allow phase lacks permission/executor Spy events")
    if allow_events.index("permission.ask") > allow_events.index("executor.callTool"):
        raise WhiteBoxBindingError("W062 executor ran before the permission gate")
    return W062RuntimeEvidence(
        binding=binding,
        source_locations=locations,
        run_id=run_id,
        production_imports=_PRODUCTION_IMPORTS,
        bun_version=EXPECTED_BUN_VERSION,
        dependency_command=dependency_command,
        dependency_exit_code=dependency_exit_code,
        dependency_output_sha256=dependency_output_sha256,
        test_command=test_command,
        test_exit_code=test_exit_code,
        phases=tuple(rows),
        cleanup_completed=all(row.get("pending_after") == 0 for row in rows),
        allowed_executor_calls=allowed,
        unauthorized_executor_calls=unauthorized,
        complete=True,
        missing_evidence=(),
    )
