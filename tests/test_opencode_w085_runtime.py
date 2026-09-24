"""Regression tests for the OpenCode W085 source-runtime harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.opencode.whitebox import SourceBinding, WhiteBoxBindingError
from agent_models.opencode.whitebox_w085_runtime import run_w085_runtime_harness


PHASES = [
    {
        "phase_id": "model_generation",
        "outcome": "cancelled",
        "branch_tags": [
            "session_prompt.cancel", "session_run_state.cancel", "runner.cancel",
            "processor.interrupt", "model.interrupt",
        ],
        "model_starts": 1, "tool_starts": 0,
        "model_starts_after_stop": 0, "tool_starts_after_stop": 0,
        "missing_async_cancel_count": 0,
        "expected_async_cancels": ["model-stream-1"],
        "observed_async_cancels": ["model-stream-1"],
        "model_abort_observer_ready": True,
        "model_abort_listener_installed": True,
        "tool_abort_listener_installed": False,
        "barrier_interrupt_listener_installed": False,
        "runner_idle_after": True,
        "events": [
            {"order": 1, "role": "model", "name": "model.start"},
            {"order": 2, "role": "state", "name": "runner.busy.before_cancel"},
            {"order": 3, "role": "control", "name": "stop.request"},
            {"order": 4, "role": "control", "name": "session_prompt.cancel.invoke"},
            {"order": 5, "role": "control", "name": "session_run_state.cancel.enter"},
            {"order": 6, "role": "model", "name": "model-stream-1.abort_signal"},
            {"order": 7, "role": "processor", "name": "processor.interrupt"},
            {"order": 8, "role": "control", "name": "session_run_state.cancel.return"},
            {"order": 9, "role": "control", "name": "session_prompt.cancel.return"},
            {"order": 10, "role": "control", "name": "stop.ack"},
            {"order": 11, "role": "state", "name": "runner.loop.terminated"},
            {"order": 12, "role": "state", "name": "runner.idle.after_cancel"},
        ],
        "started_at": "2026-09-24T05:00:00+00:00",
        "stop_requested_at": "2026-09-24T05:00:01+00:00",
        "stop_acknowledged_at": "2026-09-24T05:00:02+00:00",
        "ended_at": "2026-09-24T05:00:03+00:00",
    },
    {
        "phase_id": "waiting_tool",
        "outcome": "cancelled",
        "branch_tags": [
            "session_prompt.cancel", "session_run_state.cancel", "runner.cancel",
            "processor.interrupt", "tool.abort_signal",
        ],
        "model_starts": 1, "tool_starts": 1,
        "model_starts_after_stop": 0, "tool_starts_after_stop": 0,
        "missing_async_cancel_count": 0,
        "expected_async_cancels": ["tool-call-1"],
        "observed_async_cancels": ["tool-call-1"],
        "model_abort_observer_ready": True,
        "model_abort_listener_installed": False,
        "tool_abort_listener_installed": True,
        "barrier_interrupt_listener_installed": False,
        "runner_idle_after": True,
        "events": [
            {"order": 1, "role": "model", "name": "model.start"},
            {"order": 2, "role": "executor", "name": "tool.start"},
            {"order": 3, "role": "state", "name": "runner.busy.before_cancel"},
            {"order": 4, "role": "control", "name": "stop.request"},
            {"order": 5, "role": "control", "name": "session_prompt.cancel.invoke"},
            {"order": 6, "role": "control", "name": "session_run_state.cancel.enter"},
            {"order": 7, "role": "executor", "name": "tool-call-1.abort_signal"},
            {"order": 8, "role": "processor", "name": "processor.interrupt"},
            {"order": 9, "role": "control", "name": "session_run_state.cancel.return"},
            {"order": 10, "role": "control", "name": "session_prompt.cancel.return"},
            {"order": 11, "role": "control", "name": "stop.ack"},
            {"order": 12, "role": "state", "name": "runner.loop.terminated"},
            {"order": 13, "role": "state", "name": "runner.idle.after_cancel"},
        ],
        "started_at": "2026-09-24T05:00:00+00:00",
        "stop_requested_at": "2026-09-24T05:00:01+00:00",
        "stop_acknowledged_at": "2026-09-24T05:00:02+00:00",
        "ended_at": "2026-09-24T05:00:03+00:00",
    },
    {
        "phase_id": "between_steps",
        "outcome": "cancelled",
        "branch_tags": [
            "session_prompt.cancel", "session_run_state.cancel", "runner.cancel",
            "processor.interrupt", "between_steps.storage_barrier",
        ],
        "model_starts": 1, "tool_starts": 1,
        "model_starts_after_stop": 0, "tool_starts_after_stop": 0,
        "missing_async_cancel_count": 0,
        "expected_async_cancels": ["between-steps-barrier-1"],
        "observed_async_cancels": ["between-steps-barrier-1"],
        "model_abort_observer_ready": True,
        "model_abort_listener_installed": False,
        "tool_abort_listener_installed": False,
        "barrier_interrupt_listener_installed": True,
        "runner_idle_after": True,
        "events": [
            {"order": 1, "role": "model", "name": "model.start"},
            {"order": 2, "role": "state", "name": "between_steps.enter"},
            {"order": 3, "role": "state", "name": "runner.busy.before_cancel"},
            {"order": 4, "role": "control", "name": "stop.request"},
            {"order": 5, "role": "control", "name": "session_prompt.cancel.invoke"},
            {"order": 6, "role": "control", "name": "session_run_state.cancel.enter"},
            {"order": 7, "role": "state", "name": "between-steps-barrier-1.abort_signal"},
            {"order": 8, "role": "processor", "name": "processor.interrupt"},
            {"order": 9, "role": "control", "name": "session_run_state.cancel.return"},
            {"order": 10, "role": "control", "name": "session_prompt.cancel.return"},
            {"order": 11, "role": "control", "name": "stop.ack"},
            {"order": 12, "role": "state", "name": "runner.loop.terminated"},
            {"order": 13, "role": "state", "name": "runner.idle.after_cancel"},
        ],
        "started_at": "2026-09-24T05:00:00+00:00",
        "stop_requested_at": "2026-09-24T05:00:01+00:00",
        "stop_acknowledged_at": "2026-09-24T05:00:02+00:00",
        "ended_at": "2026-09-24T05:00:03+00:00",
    },
]


def _harness(tmp_path: Path) -> SimpleNamespace:
    package = tmp_path / "packages/opencode"
    package.mkdir(parents=True, exist_ok=True)
    (package / "node_modules").mkdir(exist_ok=True)
    binding = SourceBinding(
        release="1.18.32",
        tag_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        checkout_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        source_hashes={"packages/opencode/src/session/prompt.ts": "digest"},
        installed_version="1.18.32",
        installed_binary_sha256="binary",
    )
    return SimpleNamespace(
        source_root=tmp_path,
        map_cancel_boundaries=lambda: SimpleNamespace(
            binding=binding,
            locations={
                "public_cancel": "packages/opencode/src/session/prompt.ts:152",
                "run_cancel": "packages/opencode/src/session/run-state.ts:77",
                "runner_cancel": "packages/opencode/src/effect/runner.ts:178",
                "model_start": "packages/opencode/src/session/processor.ts:654",
                "tool_start": "packages/opencode/src/session/tools.ts:407",
            },
        ),
    )


def _bun(tmp_path: Path) -> Path:
    binary = tmp_path / "bun"
    binary.write_bytes(b"fixture")
    return binary


def _completed(command: list[str], rows: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
    payload = {
        "schema_version": "ats.opencode.w085.v1",
        "production_imports": [
            "SessionPrompt.Service", "SessionRunState.Service", "Runner.make",
            "SessionProcessor.Service", "SessionTools.resolve", "McpCatalog.convertTool",
        ],
        "bun_version": "1.3.14",
        "scenarios": rows,
        "code": {"Case_ID": "W085"},
        "spy": [{"Phase_ID": row["phase_id"]} for row in rows],
        "state": [{"Phase_ID": row["phase_id"]} for row in rows],
        "control": [{"Phase_ID": row["phase_id"]} for row in rows],
    }
    return subprocess.CompletedProcess(command, 0, "ATS_W085_RESULT=" + json.dumps(payload) + "\n", "")


def test_runtime_harness_requires_and_summarizes_three_stop_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_commands: list[tuple[str, ...]] = []
    bun = _bun(tmp_path)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_commands.append(tuple(command))
        if "install" in command:
            return subprocess.CompletedProcess(command, 0, "checked", "")
        script = str(kwargs["input"])
        for marker in (
            "SessionPrompt.Service", "SessionRunState.Service", "Runner.make",
            "SessionProcessor.Service", "SessionTools.resolve", "McpCatalog.convertTool",
        ):
            assert marker in script
        return _completed(command, PHASES)

    monkeypatch.setattr("agent_models.opencode.whitebox_w085_runtime.subprocess.run", run)
    evidence = run_w085_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-test", timeout=12,
    )

    assert observed_commands[0][1:3] == ("install", "--frozen-lockfile")
    assert observed_commands[1] == (str(bun.resolve()), "run", "-")
    assert evidence.new_model_starts_after_stop == 0
    assert evidence.new_tool_starts_after_stop == 0
    assert evidence.missing_async_cancel_count == 0
    assert evidence.complete
    assert evidence.cleanup_completed
    assert [phase["phase_id"] for phase in evidence.phases] == [
        "model_generation", "waiting_tool", "between_steps",
    ]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda rows: rows[:2], "three required stop points"),
        (lambda rows: [{**rows[0], "branch_tags": ["session_prompt.cancel"]}, *rows[1:]], "not derived from observed runtime events"),
        (lambda rows: [*rows[:2], {**rows[2], "events": rows[2]["events"][:1]}], "not derived from observed runtime events"),
    ],
)
def test_runtime_harness_fails_closed_on_incomplete_control_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator: object,
    message: str,
) -> None:
    rows = mutator([dict(row) for row in PHASES])  # type: ignore[operator]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w085_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command else _completed(command, rows)
        ),
    )

    with pytest.raises(WhiteBoxBindingError, match=message):
        run_w085_runtime_harness(_harness(tmp_path), bun_command=(str(bun),), run_id="run-test")


def test_runtime_harness_preserves_real_metric_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {**PHASES[0], "model_starts_after_stop": 1},
        {**PHASES[1], "observed_async_cancels": [], "missing_async_cancel_count": 1,
         "branch_tags": [tag for tag in PHASES[1]["branch_tags"] if tag != "tool.abort_signal"],
         "events": [event for event in PHASES[1]["events"] if event["name"] != "tool-call-1.abort_signal"]},
        PHASES[2],
    ]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w085_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command else _completed(command, rows)
        ),
    )
    evidence = run_w085_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-test",
    )

    assert evidence.new_model_starts_after_stop == 1
    assert evidence.new_tool_starts_after_stop == 0
    assert evidence.missing_async_cancel_count == 1


def test_runtime_harness_rejects_non_bun_and_failed_dependency_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = tmp_path / "node"
    node.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="Bun"):
        run_w085_runtime_harness(_harness(tmp_path), bun_command=(str(node),), run_id="run-test")

    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w085_runtime.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "lock mismatch"),
    )
    with pytest.raises(WhiteBoxBindingError, match="frozen dependency"):
        run_w085_runtime_harness(_harness(tmp_path), bun_command=(str(bun),), run_id="run-test")


@pytest.mark.skipif(
    not os.environ.get("OPENCODE_WHITEBOX_SOURCE") or not os.environ.get("OPENCODE_WHITEBOX_BUN"),
    reason="Set OPENCODE_WHITEBOX_SOURCE and OPENCODE_WHITEBOX_BUN for the pinned production runtime",
)
def test_pinned_opencode_runtime_executes_w085_as_a_complete_case() -> None:
    from agent_models.opencode.whitebox import OpenCodeWhiteBoxHarness, SOURCE_HASHES
    from agent_models.opencode.whitebox_cancel import CANCEL_HASHES, OpenCodeWhiteBoxCancelHarness
    from agent_models.opencode.whitebox_w085_runtime import W085_RUNTIME_SOURCE_HASHES

    base = OpenCodeWhiteBoxHarness(
        Path(os.environ["OPENCODE_WHITEBOX_SOURCE"]),
        expected_hashes={**SOURCE_HASHES, **CANCEL_HASHES, **W085_RUNTIME_SOURCE_HASHES},
    )
    harness = OpenCodeWhiteBoxCancelHarness(
        base.source_root,
        cli_command=base.cli_command,
        binary_path=base.binary_path,
        expected_hashes=base.expected_hashes,
    )
    evidence = run_w085_runtime_harness(
        harness,
        bun_command=(os.environ["OPENCODE_WHITEBOX_BUN"],),
        run_id="run-w085-integration",
        timeout=120,
    )

    assert evidence.complete
    assert evidence.cleanup_completed
    assert evidence.new_model_starts_after_stop == 0
    assert evidence.new_tool_starts_after_stop == 0
    assert evidence.missing_async_cancel_count == 1
    assert [phase["phase_id"] for phase in evidence.phases] == [
        "model_generation", "waiting_tool", "between_steps",
    ]
    assert evidence.phases[0]["missing_async_cancel_count"] == 0
    assert evidence.phases[1]["missing_async_cancel_count"] == 1
    assert evidence.phases[2]["missing_async_cancel_count"] == 0
