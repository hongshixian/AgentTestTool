"""Complete source-runtime harness for OpenCode white-box case W086."""

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


_SCHEMA_VERSION = "ats.opencode.w086.v1"
_PRODUCTION_IMPORTS = (
    "BackgroundJob.Service.start",
    "BackgroundJob.Service.cancel",
    "SessionRunState.Service.cancel",
)
_PHASES = ("chain", "cycle")
EXPECTED_BUN_VERSION = "1.3.14"
W086_RUNTIME_SOURCE_HASHES = {
    "bun.lock": "459a7d71db89d5e16f54b12d728ce1401da0f4b69e22053dbccc6ca04cf0e2df",
    "packages/opencode/package.json": "eb126c466ed6aee083bc42904c3f4c1d72e2821bde01e929e88c7727160eaa8f",
    "packages/core/src/background-job.ts": "d26b64a160f2fde594d4de9f2340cf3d1b6e836db98b596b9ac53d7350d21585",
    "packages/opencode/src/background/job.ts": "bc841906cab649aa6b787a2c517ca83412f2721056ad45745d5ab12a0a20f142",
    "packages/opencode/src/effect/instance-state.ts": "dbf1063a4eaa9594a44365b942a18f10cf069768c1100bd6292d3cdfbadcf259",
    "packages/opencode/src/event-v2-bridge.ts": "f12ba339dd6f268dd9ad8861fc7b2a65360f6a895eff57d83832d270ca43eb8a",
    "packages/opencode/src/session/run-state.ts": "75ed3e7f02474f4ff8ac88b5f24b75ffa7cdb9829770377e7c33d248df43936e",
    "packages/opencode/src/session/status.ts": "dbbbdee83c292379c1665a1d482b810a13754b6ae2143169b24c75ced5841b42",
    "packages/opencode/test/fixture/fixture.ts": "701086618182ad2736b876be17cbca65b896887505dad04f90525a5a48b3e52d",
}


@dataclass(frozen=True)
class W086RuntimeEvidence:
    """Structured CODE/SPY/STATE/CONTROL evidence from one W086 run."""

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
    uncancelled_child_count: int
    new_child_dispatch_count: int
    cancel_traversal_terminated: int
    cleanup_completed: bool
    complete: bool
    missing_evidence: tuple[str, ...]


_BUN_HARNESS = r'''
import { Deferred, Effect } from "effect"
import { AppNodeBuilder } from "@opencode-ai/core/effect/app-node-builder"
import { LayerNode } from "@opencode-ai/core/effect/layer-node"
import { BackgroundJob } from "__OPENCODE_ROOT__/src/background/job.ts"
import { EventV2Bridge } from "__OPENCODE_ROOT__/src/event-v2-bridge.ts"
import { SessionRunState } from "__OPENCODE_ROOT__/src/session/run-state.ts"
import { SessionStatus } from "__OPENCODE_ROOT__/src/session/status.ts"
import { withTmpdirInstance } from "__OPENCODE_ROOT__/test/fixture/fixture.ts"

const productionImports = [
  "BackgroundJob.Service.start",
  "BackgroundJob.Service.cancel",
  "SessionRunState.Service.cancel",
]

const runtimeLayer = AppNodeBuilder.build(
  LayerNode.group([BackgroundJob.node, EventV2Bridge.node, SessionStatus.node, SessionRunState.node]),
)

function graphFor(phase) {
  if (phase === "chain") {
    const root = "w086_chain_A"
    return {
      graph: "A-B-C",
      root,
      expected_child_ids: ["w086_chain_B", "w086_chain_C"],
      jobs: [
        {
          id: "w086_chain_B",
          type: "task",
          metadata: { sessionId: "w086_chain_B", parentSessionId: root },
        },
        {
          id: "w086_chain_C",
          type: "task",
          metadata: { sessionId: "w086_chain_C", parentSessionId: "w086_chain_B" },
        },
      ],
    }
  }
  if (phase === "cycle") {
    const root = "w086_cycle_A"
    return {
      graph: "A-B-A",
      root,
      expected_child_ids: ["w086_cycle_A", "w086_cycle_B"],
      jobs: [
        {
          id: "w086_cycle_A",
          type: "task",
          metadata: { sessionId: "w086_cycle_A", parentSessionId: "w086_cycle_B" },
        },
        {
          id: "w086_cycle_B",
          type: "task",
          metadata: { sessionId: "w086_cycle_B", parentSessionId: root },
        },
      ],
    }
  }
  throw new Error(`Unknown W086 phase: ${phase}`)
}

function stateByID(rows) {
  return Object.fromEntries(rows.map((row) => [row.id, row.status]))
}

async function runPhase(phase) {
  const graph = graphFor(phase)
  const unrelated = {
    id: `w086_${phase}_unrelated`,
    type: "control",
    metadata: {
      sessionId: `w086_${phase}_unrelated_session`,
      parentSessionId: `w086_${phase}_unrelated_parent`,
    },
    run: Effect.never,
  }
  const started_at = new Date().toISOString()
  const spy = {
    stage: "setup",
    order: 0,
    events: [],
    start_calls: 0,
    cancel_calls: [],
    top_level_cancel_calls: 0,
    cancel_started: false,
    starts_after_cancel: [],
    dispatch_ready_ids: [],
    dispatch_finished_ids: [],
  }
  const record = (function_role, operation, arguments_) => {
    spy.order += 1
    spy.events.push({ order: spy.order, stage: spy.stage, function_role, operation, arguments: arguments_ })
  }

  const program = withTmpdirInstance()(
    Effect.gen(function* () {
      const jobs = yield* BackgroundJob.Service
      const runState = yield* SessionRunState.Service
      const productionStart = jobs.start
      const productionCancel = jobs.cancel
      const productionTopLevelCancel = runState.cancel

      jobs.start = (input) =>
        Effect.gen(function* () {
          spy.start_calls += 1
          if (spy.cancel_started) spy.starts_after_cancel.push(input.id ?? "generated")
          record("job_registry", "BackgroundJob.start", {
            id: input.id ?? null,
            type: input.type,
            metadata: input.metadata ?? null,
          })
          const result = yield* productionStart(input)
          record("job_registry", "BackgroundJob.start.return", { id: result.id, status: result.status })
          return result
        })

      jobs.cancel = (id) =>
        Effect.gen(function* () {
          if (spy.stage === "target") spy.cancel_calls.push(id)
          record("job_canceller", "BackgroundJob.cancel", { id })
          const result = yield* productionCancel(id)
          record("job_canceller", "BackgroundJob.cancel.return", { id, status: result?.status ?? null })
          return result
        })

      runState.cancel = (sessionID) =>
        Effect.gen(function* () {
          spy.top_level_cancel_calls += 1
          spy.cancel_started = true
          record("top_level_cancel", "SessionRunState.cancel", { sessionID })
          yield* productionTopLevelCancel(sessionID)
          record("top_level_cancel", "SessionRunState.cancel.return", { sessionID })
        })

      // Prove that a running BackgroundJob can dispatch another job through the
      // exact production start boundary used by the target tasks.  A zero-call
      // target observation is meaningful only after this positive control has
      // crossed a deterministic ready/release barrier and the child is visible
      // in the real registry.
      const controlReady = yield* Deferred.make()
      const controlRelease = yield* Deferred.make()
      const controlFinished = yield* Deferred.make()
      const controlParentID = `w086_${phase}_dispatch_control_parent`
      const controlChildID = `w086_${phase}_dispatch_control_child`
      const controlRun = Effect.gen(function* () {
        yield* Deferred.succeed(controlReady, undefined)
        yield* Deferred.await(controlRelease)
        yield* jobs.start({
          id: controlChildID,
          type: "dispatch-control-child",
          metadata: { sessionId: controlChildID, parentSessionId: controlParentID },
          run: Effect.succeed("positive-control-child-complete"),
        })
        return "positive-control-parent-complete"
      }).pipe(Effect.ensuring(Deferred.succeed(controlFinished, undefined)))
      yield* jobs.start({
        id: controlParentID,
        type: "dispatch-control-parent",
        metadata: { sessionId: controlParentID, parentSessionId: `w086_${phase}_control_root` },
        run: controlRun,
      })
      const controlReadyResult = yield* Deferred.await(controlReady).pipe(Effect.timeoutOption("5 seconds"))
      yield* Deferred.succeed(controlRelease, undefined)
      const controlFinishedResult = yield* Deferred.await(controlFinished).pipe(Effect.timeoutOption("5 seconds"))
      yield* Effect.yieldNow
      const controlChild = yield* jobs.get(controlChildID)
      const positive_control_dispatch_ok =
        controlReadyResult._tag === "Some" &&
        controlFinishedResult._tag === "Some" &&
        controlChild !== undefined

      // Every target job reaches this barrier before top-level cancellation.
      // If cancellation reaches the task fiber, closing its production job
      // scope interrupts Deferred.await and the later start call is impossible.
      // If the product misses a task, releasing the barrier makes that task call
      // the real BackgroundJob.start method and the Spy records a violation.
      const dispatchRelease = yield* Deferred.make()
      const dispatchReady = new Map()
      const dispatchFinished = new Map()
      const targetInputs = []
      for (const input of graph.jobs) {
        const ready = yield* Deferred.make()
        const finished = yield* Deferred.make()
        dispatchReady.set(input.id, ready)
        dispatchFinished.set(input.id, finished)
        const childID = `${input.id}_post_cancel_child`
        const run = Effect.gen(function* () {
          spy.dispatch_ready_ids.push(input.id)
          record("task_dispatcher", "BackgroundJob.dispatch.ready", { id: input.id, child_id: childID })
          yield* Deferred.succeed(ready, undefined)
          yield* Deferred.await(dispatchRelease)
          record("task_dispatcher", "BackgroundJob.start.attempt", { id: input.id, child_id: childID })
          yield* jobs.start({
            id: childID,
            type: "post-cancel-child",
            metadata: { sessionId: childID, parentSessionId: input.id },
            run: Effect.succeed("post-cancel-child-complete"),
          })
          return "target-parent-complete"
        }).pipe(
          Effect.ensuring(
            Effect.sync(() => {
              spy.dispatch_finished_ids.push(input.id)
            }).pipe(Effect.andThen(Deferred.succeed(finished, undefined))),
          ),
        )
        targetInputs.push({ ...input, run })
      }

      for (const input of [...targetInputs, unrelated]) yield* jobs.start(input)
      const readyResult = yield* Effect.forEach(
        graph.expected_child_ids,
        (id) => Deferred.await(dispatchReady.get(id)),
        { concurrency: "unbounded", discard: true },
      ).pipe(Effect.timeoutOption("5 seconds"))
      const before = yield* jobs.list()
      const expectedBefore = [controlParentID, controlChildID, ...graph.expected_child_ids, unrelated.id]
      const positive_control_ok =
        positive_control_dispatch_ok &&
        readyResult._tag === "Some" &&
        graph.expected_child_ids.every((id) => before.find((item) => item.id === id)?.status === "running") &&
        before.find((item) => unrelated.id === item.id)?.status === "running"

      spy.stage = "target"
      const action_started_at = new Date().toISOString()
      const cancelResult = yield* runState.cancel(graph.root).pipe(Effect.timeoutOption("30 seconds"))
      const cancel_traversal_terminated = cancelResult._tag === "Some" ? 1 : 0
      const action_ack_at = new Date().toISOString()
      yield* Deferred.succeed(dispatchRelease, undefined)
      const dispatchCompletionResult = yield* Effect.forEach(
        graph.expected_child_ids,
        (id) => Deferred.await(dispatchFinished.get(id)),
        { concurrency: "unbounded", discard: true },
      ).pipe(Effect.timeoutOption("5 seconds"))
      yield* Effect.yieldNow
      const after = yield* jobs.list()
      const uncancelled_child_ids = graph.expected_child_ids.filter(
        (id) => after.find((item) => item.id === id)?.status !== "cancelled",
      )
      const unrelated_running_after = after.find((item) => item.id === unrelated.id)?.status === "running"
      const observation_end_at = new Date().toISOString()

      spy.stage = "cleanup"
      for (const item of after) {
        if (item.status === "running") yield* jobs.cancel(item.id)
      }
      const final = yield* jobs.list()
      const cleanup_remaining_running = final.filter((item) => item.status === "running").map((item) => item.id)

      jobs.start = productionStart
      jobs.cancel = productionCancel
      runState.cancel = productionTopLevelCancel

      const visitedBranchTags = [
        "background_job.real_registration",
        `cancel_traversal.${phase}`,
        "session_run_state.top_level_cancel",
      ]
      if (spy.cancel_calls.length > 0) visitedBranchTags.push("background_job.real_cancel")
      if (cancel_traversal_terminated === 1) visitedBranchTags.push("cancel_traversal.terminated")
      if (positive_control_dispatch_ok) visitedBranchTags.push("background_job.dispatch_positive_control")
      if (dispatchCompletionResult._tag === "Some") visitedBranchTags.push("background_job.post_cancel_dispatch_window")
      return {
        phase_id: phase,
        graph: graph.graph,
        root_session_id: graph.root,
        expected_child_ids: graph.expected_child_ids,
        registered_jobs: graph.jobs.map((item) => ({ id: item.id, metadata: item.metadata })),
        state_before: stateByID(before),
        state_after: stateByID(after),
        state_after_cleanup: stateByID(final),
        expected_branch_tags: [
          "background_job.real_cancel",
          "cancel_traversal.terminated",
          "background_job.dispatch_positive_control",
          "background_job.post_cancel_dispatch_window",
        ],
        branch_tags: visitedBranchTags,
        events: spy.events,
        uncalled_functions: spy.cancel_calls.length === 0 ? ["BackgroundJob.Service.cancel"] : [],
        background_start_calls: spy.start_calls,
        target_background_cancel_calls: spy.cancel_calls,
        top_level_cancel_calls: spy.top_level_cancel_calls,
        uncancelled_child_ids,
        uncancelled_child_count: uncancelled_child_ids.length,
        new_child_dispatch_ids: spy.starts_after_cancel,
        new_child_dispatch_count: spy.starts_after_cancel.length,
        positive_control_dispatch_id: controlChildID,
        positive_control_registered_ids: [controlParentID, controlChildID],
        positive_control_dispatch_observed: positive_control_dispatch_ok,
        dispatch_ready_ids: spy.dispatch_ready_ids,
        dispatch_finished_ids: spy.dispatch_finished_ids,
        dispatch_observation_completed: dispatchCompletionResult._tag === "Some",
        cancel_traversal_terminated,
        unrelated_running_after,
        cleanup_remaining_running,
        cleanup_completed: cleanup_remaining_running.length === 0,
        collector_ready: true,
        positive_control_ok,
        collection_complete: dispatchCompletionResult._tag === "Some",
        dropped_event_count: 0,
        repeat_index: 1,
        started_at,
        action_started_at,
        action_ack_at,
        observation_end_at,
        clock_source: "runtime_iso_and_effect_scheduler",
      }
    }),
  )
  return Effect.runPromise(program.pipe(Effect.provide(runtimeLayer), Effect.scoped))
}

const scenarios = []
for (const phase of ["chain", "cycle"]) scenarios.push(await runPhase(phase))
console.log(
  "ATS_W086_RESULT=" +
    JSON.stringify({
      schema_version: "ats.opencode.w086.v1",
      production_imports: productionImports,
      bun_version: Bun.version,
      scenarios,
    }),
)
'''


def run_w086_runtime_harness(
    harness: Any,
    *,
    bun_command: Sequence[str],
    run_id: str,
    timeout: float = 120,
) -> W086RuntimeEvidence:
    """Run W086 through real production registration and cancellation modules."""
    if not run_id.strip():
        raise ValueError("W086 run_id must not be empty")
    if timeout <= 0:
        raise ValueError("W086 timeout must be positive")
    if len(bun_command) != 1:
        raise ValueError("W086 runtime harness requires one explicit Bun executable")
    try:
        bun_executable = Path(bun_command[0]).resolve(strict=True)
    except OSError as error:
        raise WhiteBoxBindingError("Configured W086 Bun executable is unavailable") from error
    if not bun_executable.name.lower().startswith("bun"):
        raise ValueError("W086 runtime harness requires Bun")

    mapping = harness.map_cancel_boundaries()
    for relative, expected in W086_RUNTIME_SOURCE_HASHES.items():
        if mapping.binding.source_hashes.get(relative) != expected:
            raise WhiteBoxBindingError(f"W086 runtime source is not bound: {relative}")

    package_root = harness.source_root / "packages/opencode"
    script = _BUN_HARNESS.replace("__OPENCODE_ROOT__", package_root.resolve().as_posix())
    install_command = (
        str(bun_executable), "install", "--frozen-lockfile", "--ignore-scripts",
        "--no-progress", "--no-summary",
    )
    test_command = (str(bun_executable), "run", "-")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="opencode-w086-runtime-") as temp:
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
                f"W086 frozen dependency verification failed (exit {dependency.returncode}): {detail}"
            )
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise WhiteBoxBindingError("W086 dependency verification exhausted the case timeout")
        result = subprocess.run(
            test_command, input=script, cwd=package_root, env=isolated_env,
            capture_output=True, text=True, timeout=remaining, check=False,
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise WhiteBoxBindingError(f"W086 production runtime failed (exit {result.returncode}): {detail}")
    marker = next((line for line in result.stdout.splitlines() if line.startswith("ATS_W086_RESULT=")), None)
    if marker is None:
        raise WhiteBoxBindingError("W086 production runtime returned no structured result")
    try:
        payload = json.loads(marker.removeprefix("ATS_W086_RESULT="))
    except json.JSONDecodeError as error:
        raise WhiteBoxBindingError("W086 production runtime returned invalid JSON") from error
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
) -> W086RuntimeEvidence:
    if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
        raise WhiteBoxBindingError("W086 runtime evidence schema is invalid")
    if payload.get("production_imports") != list(_PRODUCTION_IMPORTS):
        raise WhiteBoxBindingError("W086 runtime did not import all required production modules")
    if payload.get("bun_version") != EXPECTED_BUN_VERSION:
        raise WhiteBoxBindingError("W086 runtime used an unexpected Bun version")
    rows = payload.get("scenarios")
    if (
        not isinstance(rows, list)
        or not all(isinstance(row, dict) for row in rows)
        or [row.get("phase_id") for row in rows] != list(_PHASES)
        or [row.get("graph") for row in rows] != ["A-B-C", "A-B-A"]
    ):
        raise WhiteBoxBindingError("W086 runtime must report chain and cycle phases in order")

    required_entry_tags = {"background_job.real_registration", "session_run_state.top_level_cancel"}
    for row in rows:
        phase = row["phase_id"]
        tags = row.get("branch_tags")
        if not isinstance(tags, list) or not required_entry_tags.issubset(set(tags)):
            raise WhiteBoxBindingError(f"W086 {phase} actual production branch evidence is missing")
        if f"cancel_traversal.{phase}" not in tags:
            raise WhiteBoxBindingError(f"W086 {phase} graph branch evidence is missing")
        if row.get("expected_branch_tags") != [
            "background_job.real_cancel",
            "cancel_traversal.terminated",
            "background_job.dispatch_positive_control",
            "background_job.post_cancel_dispatch_window",
        ]:
            raise WhiteBoxBindingError(f"W086 {phase} expected branch manifest is missing")
        children = row.get("expected_child_ids")
        before = row.get("state_before")
        after = row.get("state_after")
        events = row.get("events")
        cancel_calls = row.get("target_background_cancel_calls")
        registered = row.get("registered_jobs")
        if (
            not isinstance(children, list) or len(children) != 2 or len(set(children)) != 2
            or not all(isinstance(item, str) and item for item in children)
            or not isinstance(before, dict) or not isinstance(after, dict)
            or not isinstance(events, list) or not events or not isinstance(cancel_calls, list)
            or not all(isinstance(item, str) for item in cancel_calls)
            or not isinstance(registered, list)
            or {item.get("id") for item in registered if isinstance(item, dict)} != set(children)
        ):
            raise WhiteBoxBindingError(f"W086 {phase} state or Spy evidence is malformed")
        if any(before.get(child) != "running" for child in children):
            raise WhiteBoxBindingError(f"W086 {phase} did not register all children through BackgroundJob.start")
        operations = [event.get("operation") for event in events if isinstance(event, dict)]
        if (
            "BackgroundJob.start" not in operations
            or "SessionRunState.cancel" not in operations
        ):
            raise WhiteBoxBindingError(f"W086 {phase} production entry Spy is incomplete")
        if row.get("top_level_cancel_calls") != 1:
            raise WhiteBoxBindingError(f"W086 {phase} did not call the top-level cancel exactly once")
        if not row.get("collector_ready") or not row.get("collection_complete"):
            raise WhiteBoxBindingError(f"W086 {phase} collection control is incomplete")
        if (
            row.get("positive_control_ok") is not True
            or row.get("positive_control_dispatch_observed") is not True
            or row.get("unrelated_running_after") is not True
        ):
            raise WhiteBoxBindingError(f"W086 {phase} positive control failed")
        if row.get("dropped_event_count") != 0 or row.get("repeat_index") != 1:
            raise WhiteBoxBindingError(f"W086 {phase} control evidence is malformed")
        for name in ("background_start_calls", "uncancelled_child_count", "new_child_dispatch_count", "cancel_traversal_terminated"):
            value = row.get(name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise WhiteBoxBindingError(f"W086 {phase} metric {name} is malformed")
        if row["background_start_calls"] != len(children) + 3 + row["new_child_dispatch_count"]:
            raise WhiteBoxBindingError(f"W086 {phase} registration positive control is incomplete")
        uncancelled_ids = row.get("uncancelled_child_ids")
        dispatched_ids = row.get("new_child_dispatch_ids")
        ready_ids = row.get("dispatch_ready_ids")
        finished_ids = row.get("dispatch_finished_ids")
        control_dispatch_id = row.get("positive_control_dispatch_id")
        control_registered_ids = row.get("positive_control_registered_ids")
        if (
            not isinstance(uncancelled_ids, list)
            or not all(isinstance(item, str) for item in uncancelled_ids)
            or uncancelled_ids != [child for child in children if after.get(child) != "cancelled"]
            or row["uncancelled_child_count"] != len(uncancelled_ids)
            or not isinstance(dispatched_ids, list)
            or not all(isinstance(item, str) for item in dispatched_ids)
            or row["new_child_dispatch_count"] != len(dispatched_ids)
            or not isinstance(ready_ids, list)
            or set(ready_ids) != set(children)
            or len(ready_ids) != len(children)
            or not isinstance(finished_ids, list)
            or set(finished_ids) != set(children)
            or len(finished_ids) != len(children)
            or row.get("dispatch_observation_completed") is not True
            or not isinstance(control_dispatch_id, str)
            or not control_dispatch_id
            or not isinstance(control_registered_ids, list)
            or set(control_registered_ids) != {
                control_dispatch_id,
                f"w086_{phase}_dispatch_control_parent",
            }
        ):
            raise WhiteBoxBindingError(f"W086 {phase} derived metrics do not match raw state or Spy evidence")
        terminated = row["cancel_traversal_terminated"] == 1
        if row["cancel_traversal_terminated"] not in (0, 1):
            raise WhiteBoxBindingError(f"W086 {phase} termination metric must be binary")
        if terminated != ("SessionRunState.cancel.return" in operations):
            raise WhiteBoxBindingError(f"W086 {phase} termination metric does not match the top-level cancel Spy")
        if terminated != ("cancel_traversal.terminated" in tags):
            raise WhiteBoxBindingError(f"W086 {phase} termination metric does not match branch evidence")
        try:
            started_at = datetime.fromisoformat(row["started_at"])
            action_started_at = datetime.fromisoformat(row["action_started_at"])
            action_ack_at = datetime.fromisoformat(row["action_ack_at"])
            observation_end_at = datetime.fromisoformat(row["observation_end_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise WhiteBoxBindingError("W086 phase timing evidence is missing or invalid") from error
        if (
            any(value.tzinfo is None for value in (started_at, action_started_at, action_ack_at, observation_end_at))
            or not started_at <= action_started_at <= action_ack_at <= observation_end_at
        ):
            raise WhiteBoxBindingError("W086 phase timing evidence is not ordered timezone data")

    uncancelled = sum(row["uncancelled_child_count"] for row in rows)
    dispatched = sum(row["new_child_dispatch_count"] for row in rows)
    terminated = int(all(row["cancel_traversal_terminated"] == 1 for row in rows))
    return W086RuntimeEvidence(
        binding=binding, source_locations=locations, run_id=run_id,
        production_imports=_PRODUCTION_IMPORTS, bun_version=EXPECTED_BUN_VERSION,
        dependency_command=dependency_command, dependency_exit_code=dependency_exit_code,
        dependency_output_sha256=dependency_output_sha256,
        test_command=test_command, test_exit_code=test_exit_code, phases=tuple(rows),
        uncancelled_child_count=uncancelled, new_child_dispatch_count=dispatched,
        cancel_traversal_terminated=terminated,
        cleanup_completed=all(row.get("cleanup_completed") is True for row in rows),
        complete=True, missing_evidence=(),
    )
