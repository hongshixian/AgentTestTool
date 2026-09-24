"""Regression tests for the complete OpenCode W086 source-runtime harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.opencode.whitebox import SourceBinding, WhiteBoxBindingError
from agent_models.opencode.whitebox_w086_runtime import (
    EXPECTED_BUN_VERSION,
    W086_RUNTIME_SOURCE_HASHES,
    run_w086_runtime_harness,
)


def _event(order: int, operation: str) -> dict[str, object]:
    return {
        "order": order,
        "stage": "target",
        "function_role": "probe",
        "operation": operation,
        "arguments": {},
    }


def _scenario(phase: str) -> dict[str, object]:
    cycle = phase == "cycle"
    graph = "A-B-A" if cycle else "A-B-C"
    children = [f"{phase}_A", f"{phase}_B"] if cycle else [f"{phase}_B", f"{phase}_C"]
    return {
        "phase_id": phase,
        "graph": graph,
        "root_session_id": f"{phase}_A",
        "expected_child_ids": children,
        "registered_jobs": [{"id": child, "metadata": {}} for child in children],
        "state_before": {**{child: "running" for child in children}, f"{phase}_U": "running"},
        "state_after": {**{child: "cancelled" for child in children}, f"{phase}_U": "running"},
        "state_after_cleanup": {**{child: "cancelled" for child in children}, f"{phase}_U": "cancelled"},
        "branch_tags": [
            "background_job.real_registration",
            f"cancel_traversal.{phase}",
            "session_run_state.top_level_cancel",
            "background_job.real_cancel",
            "cancel_traversal.terminated",
            "background_job.dispatch_positive_control",
            "background_job.post_cancel_dispatch_window",
        ],
        "expected_branch_tags": [
            "background_job.real_cancel",
            "cancel_traversal.terminated",
            "background_job.dispatch_positive_control",
            "background_job.post_cancel_dispatch_window",
        ],
        "events": [
            _event(1, "BackgroundJob.start"),
            _event(2, "SessionRunState.cancel"),
            _event(3, "BackgroundJob.cancel"),
            _event(4, "SessionRunState.cancel.return"),
        ],
        "uncalled_functions": [],
        "background_start_calls": 5,
        "target_background_cancel_calls": children,
        "top_level_cancel_calls": 1,
        "uncancelled_child_ids": [],
        "uncancelled_child_count": 0,
        "new_child_dispatch_ids": [],
        "new_child_dispatch_count": 0,
        "positive_control_dispatch_id": f"w086_{phase}_dispatch_control_child",
        "positive_control_registered_ids": [
            f"w086_{phase}_dispatch_control_parent",
            f"w086_{phase}_dispatch_control_child",
        ],
        "positive_control_dispatch_observed": True,
        "dispatch_ready_ids": children,
        "dispatch_finished_ids": children,
        "dispatch_observation_completed": True,
        "cancel_traversal_terminated": 1,
        "unrelated_running_after": True,
        "cleanup_remaining_running": [],
        "cleanup_completed": True,
        "collector_ready": True,
        "positive_control_ok": True,
        "collection_complete": True,
        "dropped_event_count": 0,
        "repeat_index": 1,
        "started_at": "2026-09-24T08:00:00+00:00",
        "action_started_at": "2026-09-24T08:00:01+00:00",
        "action_ack_at": "2026-09-24T08:00:02+00:00",
        "observation_end_at": "2026-09-24T08:00:03+00:00",
        "clock_source": "runtime_iso_and_effect_scheduler",
    }


SCENARIOS = [_scenario("chain"), _scenario("cycle")]


def _harness(tmp_path: Path) -> SimpleNamespace:
    (tmp_path / "packages/opencode").mkdir(parents=True, exist_ok=True)
    binding = SourceBinding(
        release="1.18.32",
        tag_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        checkout_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        source_hashes=dict(W086_RUNTIME_SOURCE_HASHES),
        installed_version="1.18.32",
        installed_binary_sha256="a" * 64,
        version_binary_identity_verified=True,
    )
    mapping = SimpleNamespace(
        binding=binding,
        locations={
            "run_cancel": "packages/opencode/src/session/run-state.ts:77",
            "background_traversal": "packages/opencode/src/session/run-state.ts:111",
            "job_registration": "packages/core/src/background-job.ts:137",
            "job_cancel": "packages/core/src/background-job.ts:307",
        },
    )
    return SimpleNamespace(source_root=tmp_path, map_cancel_boundaries=lambda: mapping)


def _bun(tmp_path: Path) -> Path:
    binary = tmp_path / "bun"
    binary.write_bytes(b"fixture")
    return binary


def _completed(command: list[str], rows: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
    payload = {
        "schema_version": "ats.opencode.w086.v1",
        "production_imports": [
            "BackgroundJob.Service.start",
            "BackgroundJob.Service.cancel",
            "SessionRunState.Service.cancel",
        ],
        "bun_version": EXPECTED_BUN_VERSION,
        "scenarios": rows,
    }
    return subprocess.CompletedProcess(command, 0, "ATS_W086_RESULT=" + json.dumps(payload) + "\n", "")


def test_runtime_harness_executes_real_chain_and_cycle_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    bun = _bun(tmp_path)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        if "install" in command:
            assert kwargs["cwd"] == tmp_path
            return subprocess.CompletedProcess(command, 0, "checked", "")
        assert kwargs["cwd"] == tmp_path / "packages/opencode"
        source = str(kwargs["input"])
        assert "BackgroundJob.Service" in source
        assert "SessionRunState.Service" in source
        assert "jobs.start" in source
        assert "runState.cancel" in source
        assert "Deferred.await(dispatchRelease)" in source
        assert 'Effect.sleep("10 millis")' not in source
        return _completed(command, SCENARIOS)

    monkeypatch.setattr("agent_models.opencode.whitebox_w086_runtime.subprocess.run", run)
    evidence = run_w086_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-w086", timeout=12,
    )

    assert commands[0][1:3] == ("install", "--frozen-lockfile")
    assert commands[1] == (str(bun.resolve()), "run", "-")
    assert evidence.complete
    assert evidence.missing_evidence == ()
    assert evidence.uncancelled_child_count == 0
    assert evidence.new_child_dispatch_count == 0
    assert evidence.cancel_traversal_terminated == 1
    assert evidence.cleanup_completed
    assert [phase["graph"] for phase in evidence.phases] == ["A-B-C", "A-B-A"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda rows: rows[:1], "chain and cycle"),
        (lambda rows: [{**rows[0], "branch_tags": []}, *rows[1:]], "production branch evidence"),
        (lambda rows: [{**rows[0], "positive_control_ok": False}, *rows[1:]], "positive control failed"),
        (
            lambda rows: [{**rows[0], "positive_control_dispatch_observed": False}, *rows[1:]],
            "positive control failed",
        ),
        (
            lambda rows: [{**rows[0], "dispatch_observation_completed": False}, *rows[1:]],
            "derived metrics",
        ),
        (
            lambda rows: [{**rows[0], "dispatch_ready_ids": rows[0]["dispatch_ready_ids"][:1]}, *rows[1:]],
            "derived metrics",
        ),
        (lambda rows: [{**rows[0], "events": []}, *rows[1:]], "state or Spy evidence"),
    ],
)
def test_runtime_harness_fails_closed_on_incomplete_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator: object,
    message: str,
) -> None:
    rows = mutator([dict(row) for row in SCENARIOS])  # type: ignore[operator]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w086_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command
            else _completed(command, rows)
        ),
    )
    with pytest.raises(WhiteBoxBindingError, match=message):
        run_w086_runtime_harness(_harness(tmp_path), bun_command=(str(bun),), run_id="run-w086")


def test_runtime_harness_reports_product_metric_violations_without_discarding_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {
            **SCENARIOS[0],
            "state_after": {"chain_B": "cancelled", "chain_C": "running", "chain_U": "running"},
            "branch_tags": [
                "background_job.real_registration",
                "cancel_traversal.chain",
                "session_run_state.top_level_cancel",
                "background_job.real_cancel",
                "background_job.dispatch_positive_control",
                "background_job.post_cancel_dispatch_window",
            ],
            "events": [
                _event(1, "BackgroundJob.start"),
                _event(2, "SessionRunState.cancel"),
                _event(3, "BackgroundJob.cancel"),
            ],
            "target_background_cancel_calls": ["chain_B"],
            "uncancelled_child_ids": ["chain_C"],
            "uncancelled_child_count": 1,
            "new_child_dispatch_ids": ["chain_D"],
            "new_child_dispatch_count": 1,
            "background_start_calls": 6,
            "cancel_traversal_terminated": 0,
        },
        *SCENARIOS[1:],
    ]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w086_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command
            else _completed(command, rows)
        ),
    )
    evidence = run_w086_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-w086",
    )
    assert evidence.complete
    assert evidence.uncancelled_child_count == 1
    assert evidence.new_child_dispatch_count == 1
    assert evidence.cancel_traversal_terminated == 0


def test_runtime_harness_keeps_cleanup_failure_as_product_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{**SCENARIOS[0], "cleanup_completed": False}, *SCENARIOS[1:]]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w086_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command
            else _completed(command, rows)
        ),
    )
    evidence = run_w086_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-w086",
    )
    assert evidence.complete
    assert not evidence.cleanup_completed


def test_runtime_harness_rejects_unbound_sources_and_dependency_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bun = _bun(tmp_path)
    harness = _harness(tmp_path)
    original = harness.map_cancel_boundaries()
    incomplete_binding = SourceBinding(
        release=original.binding.release,
        tag_commit=original.binding.tag_commit,
        checkout_commit=original.binding.checkout_commit,
        source_hashes={},
        installed_version=original.binding.installed_version,
        installed_binary_sha256=original.binding.installed_binary_sha256,
    )
    harness.map_cancel_boundaries = lambda: SimpleNamespace(
        binding=incomplete_binding, locations=original.locations,
    )
    with pytest.raises(WhiteBoxBindingError, match="runtime source is not bound"):
        run_w086_runtime_harness(harness, bun_command=(str(bun),), run_id="run-w086")

    harness = _harness(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w086_runtime.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "lock mismatch"),
    )
    with pytest.raises(WhiteBoxBindingError, match="frozen dependency"):
        run_w086_runtime_harness(harness, bun_command=(str(bun),), run_id="run-w086")


def test_runtime_harness_rejects_non_bun_executable(tmp_path: Path) -> None:
    node = tmp_path / "node"
    node.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="requires Bun"):
        run_w086_runtime_harness(_harness(tmp_path), bun_command=(str(node),), run_id="run-w086")


@pytest.mark.skipif(
    not os.environ.get("OPENCODE_WHITEBOX_SOURCE") or not os.environ.get("OPENCODE_WHITEBOX_BUN"),
    reason="Set OPENCODE_WHITEBOX_SOURCE and OPENCODE_WHITEBOX_BUN for the pinned production runtime",
)
def test_pinned_opencode_runtime_executes_w086_as_a_complete_case() -> None:
    from agent_models.opencode.whitebox_cancel import CANCEL_HASHES, OpenCodeWhiteBoxCancelHarness

    evidence = run_w086_runtime_harness(
        OpenCodeWhiteBoxCancelHarness(
            Path(os.environ["OPENCODE_WHITEBOX_SOURCE"]),
            expected_hashes={**CANCEL_HASHES, **W086_RUNTIME_SOURCE_HASHES},
        ),
        bun_command=(os.environ["OPENCODE_WHITEBOX_BUN"],),
        run_id="run-w086-integration",
        timeout=120,
    )
    assert evidence.complete
    assert evidence.cleanup_completed
    assert evidence.uncancelled_child_count == 0
    assert evidence.new_child_dispatch_count == 0
    assert evidence.cancel_traversal_terminated == 1
    assert all(phase["top_level_cancel_calls"] == 1 for phase in evidence.phases)
