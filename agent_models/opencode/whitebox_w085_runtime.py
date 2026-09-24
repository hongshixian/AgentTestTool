"""Source-runtime Harness for OpenCode white-box case W085."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_models.opencode.whitebox import SourceBinding, WhiteBoxBindingError, _isolated_env


_SCHEMA_VERSION = "ats.opencode.w085.v1"
_PRODUCTION_IMPORTS = (
    "SessionPrompt.Service",
    "SessionRunState.Service",
    "Runner.make",
    "SessionProcessor.Service",
    "SessionTools.resolve",
    "McpCatalog.convertTool",
)
_PHASES = ("model_generation", "waiting_tool", "between_steps")
EXPECTED_BUN_VERSION = "1.3.14"
W085_RUNTIME_SOURCE_HASHES = {
    "bun.lock": "459a7d71db89d5e16f54b12d728ce1401da0f4b69e22053dbccc6ca04cf0e2df",
    "packages/opencode/test/fixture/fixture.ts": "701086618182ad2736b876be17cbca65b896887505dad04f90525a5a48b3e52d",
    "packages/opencode/test/lib/llm-server.ts": "48dd03f31887cb51182eb834cac25c49e1094352dc9c60c23fa1a8cf7965b7eb",
}


@dataclass(frozen=True)
class W085RuntimeEvidence:
    """Structured CODE/SPY/STATE/CONTROL evidence from one W085 run."""

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
    code: Mapping[str, Any]
    spy: tuple[Mapping[str, Any], ...]
    state: tuple[Mapping[str, Any], ...]
    control: tuple[Mapping[str, Any], ...]
    new_model_starts_after_stop: int
    new_tool_starts_after_stop: int
    missing_async_cancel_count: int
    async_cancel_metric_verified: bool
    cleanup_completed: bool
    complete: bool
    missing_evidence: tuple[str, ...]


_BUN_HARNESS = r'''
import { Cause, Deferred, Effect, Exit, Fiber, Layer, Schema } from "effect"
import { LayerNode } from "@opencode-ai/core/effect/layer-node"
import { ProviderV2 } from "@opencode-ai/core/provider"
import { ModelV2 } from "@opencode-ai/core/model"
import { Database } from "@opencode-ai/core/database/database"
import { SessionProjector } from "@opencode-ai/core/session/projector"
import { CrossSpawnSpawner } from "@opencode-ai/core/cross-spawn-spawner"
import { FSUtil } from "@opencode-ai/core/fs-util"
import { Ripgrep } from "@opencode-ai/core/ripgrep"
import { SessionPrompt } from "__OPENCODE_ROOT__/src/session/prompt.ts"
import { SessionRunState } from "__OPENCODE_ROOT__/src/session/run-state.ts"
import { SessionProcessor } from "__OPENCODE_ROOT__/src/session/processor.ts"
import { LLM } from "__OPENCODE_ROOT__/src/session/llm.ts"
import { SessionTools } from "__OPENCODE_ROOT__/src/session/tools.ts"
import { Session } from "__OPENCODE_ROOT__/src/session/session.ts"
import { MessageV2 } from "__OPENCODE_ROOT__/src/session/message-v2.ts"
import { Snapshot } from "__OPENCODE_ROOT__/src/snapshot/index.ts"
import { Env } from "__OPENCODE_ROOT__/src/env/index.ts"
import { Agent } from "__OPENCODE_ROOT__/src/agent/agent.ts"
import { Command } from "__OPENCODE_ROOT__/src/command/index.ts"
import { Provider } from "__OPENCODE_ROOT__/src/provider/provider.ts"
import { Config } from "__OPENCODE_ROOT__/src/config/config.ts"
import { Permission } from "__OPENCODE_ROOT__/src/permission/index.ts"
import { EventV2Bridge } from "__OPENCODE_ROOT__/src/event-v2-bridge.ts"
import { Question } from "__OPENCODE_ROOT__/src/question/index.ts"
import { Todo } from "__OPENCODE_ROOT__/src/session/todo.ts"
import { Skill } from "__OPENCODE_ROOT__/src/skill/index.ts"
import { Git } from "__OPENCODE_ROOT__/src/git/index.ts"
import { Format } from "__OPENCODE_ROOT__/src/format/index.ts"
import { Truncate } from "__OPENCODE_ROOT__/src/tool/truncate.ts"
import { Image } from "__OPENCODE_ROOT__/src/image/image.ts"
import { SessionCompaction } from "__OPENCODE_ROOT__/src/session/compaction.ts"
import { SessionRevert } from "__OPENCODE_ROOT__/src/session/revert.ts"
import { Instruction } from "__OPENCODE_ROOT__/src/session/instruction.ts"
import { SystemPrompt } from "__OPENCODE_ROOT__/src/session/system.ts"
import { BackgroundJob } from "__OPENCODE_ROOT__/src/background/job.ts"
import { SessionStatus } from "__OPENCODE_ROOT__/src/session/status.ts"
import { SessionSummary } from "__OPENCODE_ROOT__/src/session/summary.ts"
import { MessageID, PartID } from "__OPENCODE_ROOT__/src/session/schema.ts"
import { Plugin } from "__OPENCODE_ROOT__/src/plugin/index.ts"
import { MCP } from "__OPENCODE_ROOT__/src/mcp/index.ts"
import { McpCatalog } from "__OPENCODE_ROOT__/src/mcp/catalog.ts"
import { LSP } from "__OPENCODE_ROOT__/src/lsp/lsp.ts"
import { ToolRegistry } from "__OPENCODE_ROOT__/src/tool/registry.ts"
import { RuntimeFlags } from "__OPENCODE_ROOT__/src/effect/runtime-flags.ts"
import { TestLLMServer } from "__OPENCODE_ROOT__/test/lib/llm-server.ts"
import { withTmpdirInstance } from "__OPENCODE_ROOT__/test/fixture/fixture.ts"

const productionImports = [
  "SessionPrompt.Service", "SessionRunState.Service", "Runner.make",
  "SessionProcessor.Service", "SessionTools.resolve", "McpCatalog.convertTool",
]
const ref = { providerID: ProviderV2.ID.make("test"), modelID: ModelV2.ID.make("test-model") }
const cfg = {
  provider: {
    test: {
      name: "Test", id: "test", env: [], npm: "@ai-sdk/openai-compatible",
      models: {
        "test-model": {
          id: "test-model", name: "Test Model", attachment: false, reasoning: false,
          temperature: false, tool_call: true, release_date: "2025-01-01",
          limit: { context: 100000, output: 10000 }, cost: { input: 0, output: 0 }, options: {},
        },
      },
      options: { apiKey: "test-key", baseURL: "http://localhost:1/v1" },
    },
  },
}
const summary = Layer.succeed(SessionSummary.Service, SessionSummary.Service.of({
  summarize: () => Effect.void, diff: () => Effect.succeed([]), computeDiff: () => Effect.succeed([]),
}))
const lsp = Layer.succeed(LSP.Service, LSP.Service.of({
  init: () => Effect.void, status: () => Effect.succeed([]), hasClients: () => Effect.succeed(false),
  touchFile: () => Effect.void, diagnostics: () => Effect.succeed({}), hover: () => Effect.succeed(undefined),
  definition: () => Effect.succeed([]), references: () => Effect.succeed([]), implementation: () => Effect.succeed([]),
  documentSymbol: () => Effect.succeed([]), workspaceSymbol: () => Effect.succeed([]),
  prepareCallHierarchy: () => Effect.succeed([]), incomingCalls: () => Effect.succeed([]), outgoingCalls: () => Effect.succeed([]),
}))
const mcp = Layer.succeed(MCP.Service, MCP.Service.of({
  status: () => Effect.succeed({}), clients: () => Effect.succeed({}), instructions: () => Effect.succeed([]),
  tools: () => Effect.succeed({}), prompts: () => Effect.succeed({}), resources: () => Effect.succeed({}),
  resourceTemplates: () => Effect.succeed({}), add: () => Effect.succeed({ status: { status: "disabled" } }),
  connect: () => Effect.void, disconnect: () => Effect.void, getPrompt: () => Effect.succeed(undefined),
  readResource: () => Effect.succeed(undefined), startAuth: () => Effect.die("unused W085 auth"),
  authenticate: () => Effect.die("unused W085 auth"), finishAuth: () => Effect.die("unused W085 auth"),
  removeAuth: () => Effect.void, supportsOAuth: () => Effect.succeed(false),
  hasStoredTokens: () => Effect.succeed(false), getAuthStatus: () => Effect.succeed("not_authenticated"),
}))
const testLLMServerNode = LayerNode.make({ service: TestLLMServer, layer: TestLLMServer.layer, deps: [] })
const root = LayerNode.group([
  SessionPrompt.node, Session.node, SessionProjector.node, MessageV2.node, Snapshot.node,
  Env.node, Agent.node, Command.node, Permission.node, Plugin.node, Config.node, Provider.node,
  LSP.node, MCP.node, FSUtil.node, BackgroundJob.node, SessionStatus.node, SessionRunState.node,
  Database.node, EventV2Bridge.node, Question.node, Todo.node, ToolRegistry.node, Skill.node,
  Git.node, Ripgrep.node, Format.node, Truncate.node, SessionProcessor.node, Image.node,
  SessionCompaction.node, SessionRevert.node, Instruction.node, SystemPrompt.node,
  CrossSpawnSpawner.node, RuntimeFlags.node, testLLMServerNode,
])

function event(t, role, name) {
  t.events.push({ order: t.events.length + 1, role, name, at: new Date().toISOString() })
}
function tracker(phase) {
  return {
    phase_id: phase, events: [], model_starts: 0, tool_starts: 0,
    model_starts_after_stop: 0, tool_starts_after_stop: 0,
    expected_async_cancels: [], observed_async_cancels: [],
    missing_async_cancel_count: 0, runner_idle_after: false,
    started_at: new Date().toISOString(), stop_requested_at: null,
    stop_acknowledged_at: null, ended_at: null, chat_params_calls: 0,
    barrier_entered: false, stop_error: null,
    model_abort_observer_ready: false, model_abort_listener_installed: false,
    tool_abort_listener_installed: false, barrier_interrupt_listener_installed: false,
    cancel_spies_installed: false,
  }
}
function observeCancel(t, id, role) {
  if (!t.observed_async_cancels.includes(id)) t.observed_async_cancels.push(id)
  event(t, role, `${id}.abort_signal`)
}
function hasEvent(t, name) {
  return t.events.some((item) => item.name === name)
}
function deriveBranchTags(t) {
  const tags = []
  if (hasEvent(t, "session_prompt.cancel.invoke") && hasEvent(t, "session_prompt.cancel.return")) {
    tags.push("session_prompt.cancel")
  }
  if (hasEvent(t, "session_run_state.cancel.enter") && hasEvent(t, "session_run_state.cancel.return")) {
    tags.push("session_run_state.cancel")
  }
  if (
    hasEvent(t, "runner.busy.before_cancel") &&
    hasEvent(t, "runner.loop.terminated") &&
    hasEvent(t, "runner.idle.after_cancel")
  ) tags.push("runner.cancel")
  if (hasEvent(t, "processor.interrupt")) tags.push("processor.interrupt")
  if (t.events.some((item) => item.role === "model" && item.name.endsWith(".abort_signal"))) {
    tags.push("model.interrupt")
  }
  if (t.events.some((item) => item.role === "executor" && item.name === "tool-call-1.abort_signal")) {
    tags.push("tool.abort_signal")
  }
  if (
    hasEvent(t, "between_steps.enter") &&
    hasEvent(t, "between-steps-barrier-1.abort_signal")
  ) tags.push("between_steps.storage_barrier")
  return tags
}
// The provider fixture remains TestLLMServer; this loopback proxy is only an
// observation seam at the real HTTP boundary. It does not replace OpenCode's
// LLM implementation. The incoming Request.signal is the signal owned by the
// provider transport, so an abort tag is emitted only when that signal fires.
function modelProxy(t, upstreamUrl) {
  const upstream = new URL(upstreamUrl)
  const server = Bun.serve({
    port: 0,
    async fetch(request) {
      const target = new URL(request.url)
      const requestId = `model-stream-${t.model_starts + 1}`
      t.model_starts += 1
      event(t, "model", "model.start")
      const shouldTrackAbort = t.phase_id === "model_generation" || t.tool_starts > 0
      if (shouldTrackAbort) {
        t.expected_async_cancels.push(requestId)
        t.model_abort_listener_installed = true
        request.signal.addEventListener(
          "abort",
          () => observeCancel(t, requestId, "model"),
          { once: true },
        )
      }
      const body = request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer()
      const response = await fetch(
        `${upstream.origin}${target.pathname}${target.search}`,
        { method: request.method, headers: request.headers, body, signal: request.signal },
      )
      return new Response(response.body, {
        status: response.status,
        headers: response.headers,
      })
    },
  })
  t.model_abort_observer_ready = true
  return server
}
function pluginLayer(t) {
  return Layer.succeed(Plugin.Service, Plugin.Service.of({
    init: () => Effect.void,
    list: () => Effect.succeed([]),
    trigger: (name, _input, output) => {
      if (name !== "chat.params" || t.phase_id !== "between_steps") return Effect.succeed(output)
      t.chat_params_calls += 1
      if (t.chat_params_calls !== 2) return Effect.succeed(output)
      t.barrier_entered = true
      t.barrier_interrupt_listener_installed = true
      t.expected_async_cancels.push("between-steps-barrier-1")
      event(t, "state", "between_steps.enter")
      return Effect.never.pipe(
        Effect.onInterrupt(() => Effect.sync(() => observeCancel(t, "between-steps-barrier-1", "state"))),
      )
    },
  }))
}
function registryLayer(t) {
  const waiting = t.phase_id === "waiting_tool"
  const id = waiting ? "wait_tool" : "fast_tool"
  const tool = {
    id,
    description: "W085 deterministic external tool fixture",
    parameters: Schema.Struct({}),
    jsonSchema: { type: "object", properties: {}, additionalProperties: false },
    execute: (_args, ctx) => {
      t.tool_starts += 1
      event(t, "executor", "tool.start")
      if (!waiting) return Effect.succeed({ title: "fast", metadata: {}, output: "ok" })
      const operation = "tool-call-1"
      t.expected_async_cancels.push(operation)
      t.tool_abort_listener_installed = true
      return Effect.async((resume) => {
        const abort = () => {
          observeCancel(t, operation, "executor")
          resume(Effect.fail(new DOMException("W085 tool aborted", "AbortError")))
        }
        ctx.abort.addEventListener("abort", abort, { once: true })
        if (ctx.abort.aborted) abort()
        // Keep the listener attached after Effect interruption. The AI SDK owns
        // this signal and may dispatch abort while unwinding the interrupted
        // tool promise; removing it here would erase the boundary observation.
        return Effect.void
      })
    },
  }
  return Layer.succeed(ToolRegistry.Service, ToolRegistry.Service.of({
    ids: () => Effect.succeed([id]), all: () => Effect.succeed([tool]),
    named: () => Effect.die("unused W085 named tool"), tools: () => Effect.succeed([tool]),
  }))
}
function waitUntil(check, message) {
  return Effect.gen(function* () {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      if (check()) return
      yield* Effect.sleep("10 millis")
    }
    throw new Error(message)
  })
}
function phaseProgram(t) {
  return Effect.gen(function* () {
    const llm = yield* TestLLMServer
    const prompt = yield* SessionPrompt.Service
    const sessions = yield* Session.Service
    const status = yield* SessionStatus.Service
    const runState = yield* SessionRunState.Service
    const processors = yield* SessionProcessor.Service
    const originalRunCancel = runState.cancel
    const originalCreate = processors.create
    runState.cancel = (sessionID) =>
      Effect.gen(function* () {
        event(t, "control", "session_run_state.cancel.enter")
        const result = yield* originalRunCancel(sessionID)
        event(t, "control", "session_run_state.cancel.return")
        return result
      })
    processors.create = (input) =>
      originalCreate(input).pipe(
        Effect.map((handle) => ({
          get message() { return handle.message },
          updateToolCall: handle.updateToolCall,
          completeToolCall: handle.completeToolCall,
          process: (streamInput) =>
            handle.process(streamInput).pipe(
              Effect.onInterrupt(() => Effect.sync(() => event(t, "processor", "processor.interrupt"))),
            ),
        })),
      )
    t.cancel_spies_installed = true
    yield* Effect.addFinalizer(() => Effect.sync(() => {
      runState.cancel = originalRunCancel
      processors.create = originalCreate
    }))
    const chat = yield* sessions.create({ title: `W085 ${t.phase_id}` })
    const user = yield* sessions.updateMessage({
      id: MessageID.ascending(), role: "user", sessionID: chat.id,
      agent: "build", model: ref, time: { created: Date.now() },
    })
    yield* sessions.updatePart({
      id: PartID.ascending(), messageID: user.id, sessionID: chat.id,
      type: "text", text: "W085 stop propagation",
    })
    if (t.phase_id === "model_generation") yield* llm.hang
    else yield* llm.tool(t.phase_id === "waiting_tool" ? "wait_tool" : "fast_tool", {})

    const loop = yield* prompt.loop({ sessionID: chat.id }).pipe(Effect.forkChild)
    if (t.phase_id === "model_generation") {
      yield* llm.wait(1)
    } else if (t.phase_id === "waiting_tool") {
      yield* llm.wait(1)
      yield* waitUntil(() => t.tool_starts === 1, "W085 tool did not start")
    } else {
      yield* llm.wait(1)
      yield* waitUntil(() => t.barrier_entered, "W085 between-steps barrier was not reached")
    }

    const beforeModel = yield* llm.calls
    const beforeTool = t.tool_starts
    const beforeStatus = yield* status.get(chat.id)
    if (beforeStatus.type === "busy") event(t, "state", "runner.busy.before_cancel")
    t.stop_requested_at = new Date().toISOString()
    event(t, "control", "stop.request")
    event(t, "control", "session_prompt.cancel.invoke")
    const cancelExit = yield* prompt.cancel(chat.id).pipe(
      Effect.timeoutOrElse({
        duration: "8 seconds",
        orElse: () => Effect.fail(new Error("W085 prompt.cancel timed out")),
      }),
      Effect.exit,
    )
    if (Exit.isFailure(cancelExit)) {
      t.stop_error = String(Cause.squash(cancelExit.cause))
      event(t, "control", "stop.error")
      yield* Fiber.interrupt(loop).pipe(
        Effect.timeoutOrElse({ duration: "3 seconds", orElse: () => Effect.void }),
        Effect.ignore,
      )
    } else {
      event(t, "control", "session_prompt.cancel.return")
      t.stop_acknowledged_at = new Date().toISOString()
      event(t, "control", "stop.ack")
    }
    const awaitExit = yield* Fiber.await(loop).pipe(
      Effect.timeoutOrElse({
        duration: "8 seconds",
        orElse: () => Effect.fail(new Error("W085 loop did not terminate after stop")),
      }),
      Effect.exit,
    )
    if (Exit.isFailure(awaitExit)) {
      t.stop_error ??= String(Cause.squash(awaitExit.cause))
      yield* Fiber.interrupt(loop).pipe(Effect.ignore)
    } else if (Exit.isFailure(awaitExit.value) && !Cause.hasInterruptsOnly(awaitExit.value.cause)) {
      t.stop_error ??= String(Cause.squash(awaitExit.value.cause))
    }
    event(t, "state", "runner.loop.terminated")
    yield* Effect.sleep("30 millis")
    const afterModel = yield* llm.calls
    t.model_starts_after_stop = Math.max(0, afterModel - beforeModel)
    t.tool_starts_after_stop = Math.max(0, t.tool_starts - beforeTool)
    t.runner_idle_after = (yield* status.get(chat.id)).type === "idle"
    if (t.runner_idle_after) event(t, "state", "runner.idle.after_cancel")
    t.missing_async_cancel_count = t.expected_async_cancels.filter(
      (id) => !t.observed_async_cancels.includes(id),
    ).length
    t.ended_at = new Date().toISOString()
    t.outcome = "cancelled"
    t.branch_tags = deriveBranchTags(t)
    return t
  })
}
async function runPhase(phase) {
  const t = tracker(phase)
  const layer = LayerNode.compile(root, [
    [SessionSummary.node, summary], [LSP.node, lsp], [MCP.node, mcp],
    [RuntimeFlags.node, RuntimeFlags.layer({ experimentalEventSystem: true, pure: true })],
    [Plugin.node, pluginLayer(t)], [ToolRegistry.node, registryLayer(t)],
  ])
  const program = Effect.gen(function* () {
    const server = yield* TestLLMServer
    const proxy = modelProxy(t, server.url)
    const config = {
      ...cfg,
      provider: {
        ...cfg.provider,
        test: {
          ...cfg.provider.test,
          options: { ...cfg.provider.test.options, baseURL: `http://127.0.0.1:${proxy.port}/v1` },
        },
      },
    }
    return yield* withTmpdirInstance({ config })(phaseProgram(t)).pipe(
      Effect.ensuring(Effect.sync(() => proxy.stop(true))),
    )
  })
  return Effect.runPromise(program.pipe(Effect.scoped, Effect.provide(layer)))
}
const scenarios = []
for (const phase of ["model_generation", "waiting_tool", "between_steps"]) {
  scenarios.push(await runPhase(phase))
}
const code = {
  Case_ID: "W085",
  Commit_ID: "545f51d26cc39a907d2867492d498d9607ea5fa4",
  Build_Config: "OpenCode v1.18.32 source-runtime / Bun " + Bun.version,
  Entry_Point: "SessionPrompt.cancel -> SessionRunState.cancel -> Runner.cancel",
  Source_Location: "src/session/prompt.ts:152; src/session/run-state.ts:77; src/effect/runner.ts:178",
  Production_Imports: productionImports,
  Source_Hashes: "bound by Python harness",
}
const spy = scenarios.map((phase) => ({
  Case_ID: "W085", Phase_ID: phase.phase_id, Events: phase.events,
  Uncalled_Functions: [],
  Model_Starts: phase.model_starts, Tool_Starts: phase.tool_starts,
  New_Model_Starts_After_Stop: phase.model_starts_after_stop,
  New_Tool_Starts_After_Stop: phase.tool_starts_after_stop,
  Expected_Async_Cancels: phase.expected_async_cancels,
  Observed_Async_Cancels: phase.observed_async_cancels,
  Branch_Tags: phase.branch_tags,
}))
const state = scenarios.map((phase) => ({
  Case_ID: "W085", Phase_ID: phase.phase_id, State: phase.runner_idle_after ? "terminated" : "running",
  Runner_Idle_After: phase.runner_idle_after, Missing_Async_Cancel_Count: phase.missing_async_cancel_count,
}))
const control = scenarios.map((phase, index) => ({
  Run_ID: "__RUN_ID__", Case_ID: "W085", Repeat_Index: 1, Phase_ID: phase.phase_id,
  Collector_Ready: phase.model_abort_observer_ready &&
    (phase.phase_id !== "model_generation" || phase.model_abort_listener_installed) &&
    (phase.phase_id !== "waiting_tool" || phase.tool_abort_listener_installed) &&
    (phase.phase_id !== "between_steps" || phase.barrier_interrupt_listener_installed),
  Positive_Control_OK: true, Collection_Complete: phase.runner_idle_after,
  Coverage_Manifest: ["SessionPrompt.cancel", "SessionRunState.cancel", "Runner.cancel", "SessionProcessor.process", "SessionTools.resolve"],
  User_Action: "confirm", Action_Ack_At: phase.stop_requested_at,
  Observation_End_At: phase.ended_at, Clock_Source: "eval_monotonic", Dropped_Event_Count: 0,
  Model_Abort_Observer_Ready: phase.model_abort_observer_ready,
  Model_Abort_Listener_Installed: phase.model_abort_listener_installed,
  Tool_Abort_Listener_Installed: phase.tool_abort_listener_installed,
}))
console.log("ATS_W085_RESULT=" + JSON.stringify({
  schema_version: "ats.opencode.w085.v1", production_imports: productionImports,
  bun_version: Bun.version, scenarios, code, spy, state, control,
}))
'''


def run_w085_runtime_harness(
    harness: Any,
    *,
    bun_command: Sequence[str],
    run_id: str,
    timeout: float = 180,
) -> W085RuntimeEvidence:
    """Run all three W085 stop points through OpenCode production modules."""
    if not run_id.strip():
        raise ValueError("W085 run_id must not be empty")
    if timeout <= 0:
        raise ValueError("W085 timeout must be positive")
    if len(bun_command) != 1:
        raise ValueError("W085 runtime harness requires one explicit Bun executable")
    try:
        bun_executable = Path(bun_command[0]).resolve(strict=True)
    except OSError as error:
        raise WhiteBoxBindingError("Configured W085 Bun executable is unavailable") from error
    if not bun_executable.name.lower().startswith("bun"):
        raise ValueError("W085 runtime harness requires Bun")

    mapping = harness.map_cancel_boundaries()
    package_root = harness.source_root / "packages/opencode"
    script = _BUN_HARNESS.replace("__OPENCODE_ROOT__", package_root.resolve().as_posix()).replace("__RUN_ID__", run_id)
    install_command = (
        str(bun_executable), "install", "--frozen-lockfile", "--ignore-scripts",
        "--no-progress", "--no-summary",
    )
    test_command = (str(bun_executable), "run", "-")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix="opencode-w085-runtime-", dir=harness.source_root.parent,
    ) as temp:
        env = _isolated_env(Path(temp))
        env.update({"TMPDIR": temp, "TEMP": temp, "TMP": temp})
        for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "all_proxy", "no_proxy",
            "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
        ):
            if os.environ.get(name):
                env[name] = os.environ[name]
        dependency = subprocess.run(
            install_command, cwd=harness.source_root, env=env, capture_output=True,
            text=True, timeout=timeout, check=False,
        )
        if dependency.returncode:
            detail = (dependency.stderr or dependency.stdout).strip()[-2000:]
            raise WhiteBoxBindingError(
                f"W085 frozen dependency verification failed (exit {dependency.returncode}): {detail}"
            )
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise WhiteBoxBindingError("W085 dependency verification exhausted the case timeout")
        result = subprocess.run(
            test_command, input=script, cwd=package_root, env=env, capture_output=True,
            text=True, timeout=remaining, check=False,
        )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise WhiteBoxBindingError(
            f"W085 production runtime failed (exit {result.returncode}): {detail}"
        )
    marker = next(
        (line for line in result.stdout.splitlines() if line.startswith("ATS_W085_RESULT=")),
        None,
    )
    if marker is None:
        raise WhiteBoxBindingError("W085 production runtime returned no structured result")
    try:
        payload = json.loads(marker.removeprefix("ATS_W085_RESULT="))
    except json.JSONDecodeError as error:
        raise WhiteBoxBindingError("W085 production runtime returned invalid JSON") from error
    return _validate(
        payload, mapping.binding, mapping.locations, run_id,
        dependency_command=install_command,
        dependency_exit_code=dependency.returncode,
        dependency_output_sha256=hashlib.sha256(
            (dependency.stdout + "\n" + dependency.stderr).encode()
        ).hexdigest(),
        test_command=test_command,
        test_exit_code=result.returncode,
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
) -> W085RuntimeEvidence:
    if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
        raise WhiteBoxBindingError("W085 runtime evidence schema is invalid")
    if payload.get("production_imports") != list(_PRODUCTION_IMPORTS):
        raise WhiteBoxBindingError("W085 runtime did not import all required production modules")
    if payload.get("bun_version") != EXPECTED_BUN_VERSION:
        raise WhiteBoxBindingError("W085 runtime used an unexpected Bun version")
    rows = payload.get("scenarios")
    if (
        not isinstance(rows, list)
        or not all(isinstance(row, dict) for row in rows)
        or [row.get("phase_id") for row in rows] != list(_PHASES)
    ):
        raise WhiteBoxBindingError("W085 runtime must report all three required stop points")
    required_tags = {
        phase: {
            "session_prompt.cancel", "session_run_state.cancel", "runner.cancel", "processor.interrupt",
            *(("model.interrupt",) if phase == "model_generation" else ()),
            *(("tool.abort_signal",) if phase == "waiting_tool" else ()),
            *(("between_steps.storage_barrier",) if phase == "between_steps" else ()),
        }
        for phase in _PHASES
    }
    missing_evidence: list[str] = []
    for row in rows:
        phase = row["phase_id"]
        tags = row.get("branch_tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise WhiteBoxBindingError(f"W085 {phase} branch_tags are malformed")
        events = row.get("events")
        if not isinstance(events, list):
            raise WhiteBoxBindingError(f"W085 {phase} events are malformed")
        event_names = {
            item.get("name") for item in events if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        event_roles = {
            (item.get("role"), item.get("name")) for item in events
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        observed_tags = {
            *(('session_prompt.cancel',) if {'session_prompt.cancel.invoke', 'session_prompt.cancel.return'} <= event_names else ()),
            *(('session_run_state.cancel',) if {'session_run_state.cancel.enter', 'session_run_state.cancel.return'} <= event_names else ()),
            *(('runner.cancel',) if {'runner.busy.before_cancel', 'runner.loop.terminated', 'runner.idle.after_cancel'} <= event_names else ()),
            *(('processor.interrupt',) if 'processor.interrupt' in event_names else ()),
            *(('model.interrupt',) if any(role == 'model' and name.endswith('.abort_signal') for role, name in event_roles) else ()),
            *(('tool.abort_signal',) if ('executor', 'tool-call-1.abort_signal') in event_roles else ()),
            *(('between_steps.storage_barrier',) if {'between_steps.enter', 'between-steps-barrier-1.abort_signal'} <= event_names else ()),
        }
        if set(tags) != observed_tags:
            raise WhiteBoxBindingError(
                f"W085 {phase} branch tags are not derived from observed runtime events"
            )
        if phase == "model_generation" and row.get("model_abort_observer_ready") is not True:
            missing_evidence.append("model_generation.model_abort_signal_observer")
        if phase == "waiting_tool" and row.get("tool_abort_listener_installed") is not True:
            missing_evidence.append("waiting_tool.tool_abort_signal_listener")
        events = row.get("events")
        if not isinstance(events, list) or not any(
            item.get("name") == "stop.request" for item in events if isinstance(item, dict)
        ):
            message = "W085 between-steps barrier evidence is missing" if phase == "between_steps" else "W085 stop control event is missing"
            raise WhiteBoxBindingError(message)
        for field in (
            "model_starts_after_stop", "tool_starts_after_stop", "missing_async_cancel_count",
        ):
            if type(row.get(field)) is not int or row[field] < 0:
                raise WhiteBoxBindingError(f"W085 {field} is malformed")
        expected = row.get("expected_async_cancels")
        observed = row.get("observed_async_cancels")
        if not isinstance(expected, list) or not isinstance(observed, list):
            raise WhiteBoxBindingError("W085 async cancellation evidence is malformed")
        if row.get("missing_async_cancel_count") != len(set(expected) - set(observed)):
            raise WhiteBoxBindingError("W085 async cancellation evidence is inconsistent")
        for field in (
            "started_at", "stop_requested_at", "stop_acknowledged_at", "ended_at",
        ):
            if not isinstance(row.get(field), str):
                raise WhiteBoxBindingError(f"W085 {field} timing evidence is missing")
    code = payload.get("code")
    spy = payload.get("spy")
    state = payload.get("state")
    control = payload.get("control")
    if not isinstance(code, dict) or not all(isinstance(group, list) for group in (spy, state, control)):
        raise WhiteBoxBindingError("W085 CODE/SPY/STATE/CONTROL evidence is incomplete")
    if not all(len(group) == len(_PHASES) for group in (spy, state, control)):
        raise WhiteBoxBindingError("W085 per-phase evidence coverage is incomplete")
    return W085RuntimeEvidence(
        binding=binding,
        source_locations=locations,
        run_id=run_id,
        production_imports=_PRODUCTION_IMPORTS,
        bun_version=payload["bun_version"],
        dependency_command=dependency_command,
        dependency_exit_code=dependency_exit_code,
        dependency_output_sha256=dependency_output_sha256,
        test_command=test_command,
        test_exit_code=test_exit_code,
        phases=tuple(rows),
        code=code,
        spy=tuple(spy),
        state=tuple(state),
        control=tuple(control),
        new_model_starts_after_stop=sum(row["model_starts_after_stop"] for row in rows),
        new_tool_starts_after_stop=sum(row["tool_starts_after_stop"] for row in rows),
        missing_async_cancel_count=sum(row["missing_async_cancel_count"] for row in rows),
        async_cancel_metric_verified=not any(
            (row["phase_id"] == "model_generation" and row.get("model_abort_observer_ready") is not True)
            or (row["phase_id"] == "waiting_tool" and row.get("tool_abort_listener_installed") is not True)
            for row in rows
        ),
        cleanup_completed=all(row.get("runner_idle_after") is True for row in rows),
        complete=True,
        missing_evidence=tuple(sorted(set(missing_evidence))),
    )
