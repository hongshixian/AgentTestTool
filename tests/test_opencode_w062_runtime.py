"""Regression tests for the complete OpenCode W062 source-runtime harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.opencode.whitebox import SourceBinding, WhiteBoxBindingError
from agent_models.opencode.whitebox_w062_runtime import run_w062_runtime_harness


SCENARIOS = [
    {
        "phase_id": "allow",
        "outcome": "allowed",
        "branch_tags": ["permission.allow", "dispatcher.execute"],
        "permission_calls": 1,
        "executor_calls": 1,
        "pending_before_reply": 0,
        "pending_after": 0,
        "events": ["permission.ask", "executor.callTool"],
        "started_at": "2026-09-24T05:00:00+00:00",
        "ended_at": "2026-09-24T05:00:01+00:00",
    },
    {
        "phase_id": "deny",
        "outcome": "denied",
        "branch_tags": ["permission.deny"],
        "permission_calls": 1,
        "executor_calls": 0,
        "pending_before_reply": 0,
        "pending_after": 0,
        "events": ["permission.ask"],
        "started_at": "2026-09-24T05:00:00+00:00",
        "ended_at": "2026-09-24T05:00:01+00:00",
    },
    {
        "phase_id": "not_listed",
        "outcome": "rejected",
        "branch_tags": ["permission.ask", "permission.reply.reject"],
        "permission_calls": 1,
        "executor_calls": 0,
        "pending_before_reply": 1,
        "pending_after": 0,
        "events": ["permission.ask", "permission.pending", "permission.reply.reject"],
        "started_at": "2026-09-24T05:00:00+00:00",
        "ended_at": "2026-09-24T05:00:01+00:00",
    },
    {
        "phase_id": "error",
        "outcome": "authorization_error",
        "branch_tags": ["permission.error"],
        "permission_calls": 1,
        "executor_calls": 0,
        "pending_before_reply": 0,
        "pending_after": 0,
        "events": ["permission.ask"],
        "started_at": "2026-09-24T05:00:00+00:00",
        "ended_at": "2026-09-24T05:00:01+00:00",
    },
]


def _harness(tmp_path: Path) -> SimpleNamespace:
    package = tmp_path / "packages/opencode"
    package.mkdir(parents=True)
    (package / "node_modules").mkdir()
    binding = SourceBinding(
        release="1.18.32",
        tag_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        checkout_commit="545f51d26cc39a907d2867492d498d9607ea5fa4",
        source_hashes={"packages/opencode/src/session/tools.ts": "digest"},
        installed_version="1.18.32",
        installed_binary_sha256="binary",
    )
    return SimpleNamespace(
        source_root=tmp_path,
        map_permission_dispatch_boundary=lambda: SimpleNamespace(
            binding=binding,
            locations={
                "permission_allow": "packages/opencode/src/permission/index.ts:43",
                "permission_deny": "packages/opencode/src/permission/index.ts:38",
                "dispatcher_permission": "packages/opencode/src/session/tools.ts:65",
                "dispatcher_executor": "packages/opencode/src/session/tools.ts:401",
            },
        ),
    )


def _bun(tmp_path: Path) -> Path:
    binary = tmp_path / "bun"
    binary.write_bytes(b"fixture")
    return binary


def _completed(command: list[str], rows: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
    payload = {
        "schema_version": "ats.opencode.w062.v1",
        "production_imports": ["Permission.Service", "SessionTools.resolve", "McpCatalog.convertTool"],
        "bun_version": "1.3.14",
        "scenarios": rows,
    }
    return subprocess.CompletedProcess(command, 0, "ATS_W062_RESULT=" + json.dumps(payload) + "\n", "")


def test_runtime_harness_requires_and_summarizes_all_four_production_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_commands: list[tuple[str, ...]] = []
    bun = _bun(tmp_path)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_commands.append(tuple(command))
        if "install" in command:
            assert kwargs["cwd"] == tmp_path
            return subprocess.CompletedProcess(command, 0, "checked", "")
        assert kwargs["cwd"] == tmp_path / "packages/opencode"
        assert "SessionTools.resolve" in str(kwargs["input"])
        assert "Permission.Service" in str(kwargs["input"])
        assert "McpCatalog.convertTool" in str(kwargs["input"])
        return _completed(command, SCENARIOS)

    monkeypatch.setattr("agent_models.opencode.whitebox_w062_runtime.subprocess.run", run)
    evidence = run_w062_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-test", timeout=12,
    )

    assert observed_commands[0][1:3] == ("install", "--frozen-lockfile")
    assert observed_commands[1] == (str(bun.resolve()), "run", "-")
    assert evidence.allowed_executor_calls == 1
    assert evidence.unauthorized_executor_calls == 0
    assert evidence.complete
    assert evidence.missing_evidence == ()
    assert [phase["phase_id"] for phase in evidence.phases] == ["allow", "deny", "not_listed", "error"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda rows: rows[:3], "four required phases"),
        (lambda rows: [{**rows[0], "branch_tags": []}, *rows[1:]], "permission branch"),
    ],
)
def test_runtime_harness_fails_closed_on_incomplete_or_unsafe_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator: object,
    message: str,
) -> None:
    rows = mutator([dict(row) for row in SCENARIOS])  # type: ignore[operator]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w062_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command else _completed(command, rows)
        ),
    )

    with pytest.raises(WhiteBoxBindingError, match=message):
        run_w062_runtime_harness(_harness(tmp_path), bun_command=(str(bun),), run_id="run-test")


def test_runtime_harness_returns_cleanup_failure_as_product_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{**SCENARIOS[0], "pending_after": 1}, *SCENARIOS[1:]]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w062_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command else _completed(command, rows)
        ),
    )

    evidence = run_w062_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-test",
    )

    assert evidence.complete
    assert not evidence.cleanup_completed


def test_runtime_harness_reports_metric_violations_instead_of_dropping_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [*SCENARIOS[:1], {**SCENARIOS[1], "executor_calls": 1}, *SCENARIOS[2:]]
    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w062_runtime.subprocess.run",
        lambda command, **kwargs: (
            subprocess.CompletedProcess(command, 0, "checked", "")
            if "install" in command else _completed(command, rows)
        ),
    )

    evidence = run_w062_runtime_harness(
        _harness(tmp_path), bun_command=(str(bun),), run_id="run-test",
    )

    assert evidence.complete
    assert evidence.unauthorized_executor_calls == 1


def test_runtime_harness_rejects_non_bun_or_failed_frozen_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    node = tmp_path / "node"
    node.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="Bun"):
        run_w062_runtime_harness(harness, bun_command=(str(node),), run_id="run-test")

    bun = _bun(tmp_path)
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w062_runtime.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "lock mismatch"),
    )
    with pytest.raises(WhiteBoxBindingError, match="frozen dependency"):
        run_w062_runtime_harness(harness, bun_command=(str(bun),), run_id="run-test")


@pytest.mark.skipif(
    not os.environ.get("OPENCODE_WHITEBOX_SOURCE") or not os.environ.get("OPENCODE_WHITEBOX_BUN"),
    reason="Set OPENCODE_WHITEBOX_SOURCE and OPENCODE_WHITEBOX_BUN for the pinned production runtime",
)
def test_pinned_opencode_runtime_executes_w062_as_a_complete_case() -> None:
    from agent_models.opencode.whitebox import OpenCodeWhiteBoxHarness, SOURCE_HASHES
    from agent_models.opencode.whitebox_w062_runtime import W062_RUNTIME_SOURCE_HASHES

    evidence = run_w062_runtime_harness(
        OpenCodeWhiteBoxHarness(
            Path(os.environ["OPENCODE_WHITEBOX_SOURCE"]),
            expected_hashes={**SOURCE_HASHES, **W062_RUNTIME_SOURCE_HASHES},
        ),
        bun_command=(os.environ["OPENCODE_WHITEBOX_BUN"],),
        run_id="run-w062-integration",
        timeout=120,
    )

    assert evidence.complete
    assert evidence.cleanup_completed
    assert evidence.allowed_executor_calls == 1
    assert evidence.unauthorized_executor_calls == 0
    assert all(phase["pending_after"] == 0 for phase in evidence.phases)
