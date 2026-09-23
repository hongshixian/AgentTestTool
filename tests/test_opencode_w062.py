"""Offline regression of OpenCode's pinned W062 dispatch probe."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.opencode.whitebox import (
    BuildEvidence,
    OpenCodeWhiteBoxHarness,
    SourceBinding,
    WhiteBoxBindingError,
)
from agent_models.opencode.whitebox_w062 import probe_w062_dispatch


SCENARIOS = [
    {"name": "allow", "outcome": "ok", "pending_after": 0,
     "order": ["tool.execute.before", "permission.ask", "permission.rule_allow", "permission.ended", "executor", "tool.execute.after"]},
    {"name": "deny", "outcome": "DeniedError", "pending_after": 0,
     "order": ["tool.execute.before", "permission.ask", "permission.rule_deny", "permission.ended"]},
    {"name": "not_listed", "outcome": "RejectedError", "pending_after": 0,
     "order": ["tool.execute.before", "permission.ask", "permission.rule_ask", "permission.asked", "permission.ended"]},
    {"name": "error", "outcome": "TypeError", "pending_after": 0,
     "order": ["tool.execute.before", "permission.ask", "permission.ended"]},
]

SOURCE_FILES = (
    "packages/opencode/src/permission/index.ts",
    "packages/core/src/util/wildcard.ts",
    "packages/opencode/src/session/tools.ts",
)


def _harness(tmp_path: Path) -> SimpleNamespace:
    hashes = {}
    for relative in SOURCE_FILES:
        source = tmp_path / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"pinned {relative}\n", encoding="utf-8")
        hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    binding = SourceBinding(
        release="1.18.32", tag_commit="pinned", checkout_commit="pinned",
        source_hashes=hashes, installed_version="1.18.32", installed_binary_sha256="binary-digest",
    )
    return SimpleNamespace(
        source_root=tmp_path, node_command=("node",),
        map_permission_dispatch_boundary=lambda: SimpleNamespace(
            binding=binding, locations={"dispatcher_executor": "session/tools.ts:111"},
        ),
    )


def _response(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]]) -> None:
    monkeypatch.setattr(
        "agent_models.opencode.whitebox_w062.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(rows)),
    )


def test_dispatch_probe_records_call_counts_but_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _response(monkeypatch, SCENARIOS)
    probe = probe_w062_dispatch(_harness(tmp_path))

    assert probe.allowed_executor_calls == 1
    assert probe.unauthorized_executor_calls == 0
    assert [item["outcome"] for item in probe.scenarios] == [
        "ok", "DeniedError", "RejectedError", "TypeError",
    ]
    assert not probe.matched_build
    assert "instrumented full production runtime" in probe.missing_for_full_case[1]


def test_dispatch_probe_requires_binary_identity_not_only_build_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _response(monkeypatch, SCENARIOS)
    build = BuildEvidence(
        command=("bun", "build"), artifact="opencode", artifact_sha256="different",
        repetitions=2, matches_installed_binary=True,
    )
    probe = probe_w062_dispatch(_harness(tmp_path), build=build)

    assert not probe.matched_build
    assert "reproducible build matching deployed binary" in probe.missing_for_full_case


def test_dispatch_probe_does_not_trust_self_reported_build_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _response(monkeypatch, SCENARIOS)
    build = BuildEvidence(
        command=("never-executed",), artifact="unverified",
        artifact_sha256="binary-digest", repetitions=2, matches_installed_binary=True,
    )

    probe = probe_w062_dispatch(_harness(tmp_path), build=build)

    assert not probe.matched_build
    assert "reproducible build matching deployed binary" in probe.missing_for_full_case


def test_dispatch_probe_executes_only_verified_private_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    original = [(tmp_path / relative).read_bytes() for relative in SOURCE_FILES]

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        paths = [Path(item) for item in command[-len(SOURCE_FILES):]]
        assert all(path.is_relative_to(Path(str(kwargs["cwd"]))) for path in paths)
        (tmp_path / SOURCE_FILES[0]).write_text("changed after snapshot\n", encoding="utf-8")
        assert [path.read_bytes() for path in paths] == original
        return subprocess.CompletedProcess(command, 0, json.dumps(SCENARIOS))

    monkeypatch.setattr("agent_models.opencode.whitebox_w062.subprocess.run", run)
    assert probe_w062_dispatch(harness).allowed_executor_calls == 1


def test_dispatch_probe_rejects_checkout_change_after_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    original_map = harness.map_permission_dispatch_boundary

    def changed_map() -> SimpleNamespace:
        mapping = original_map()
        (tmp_path / SOURCE_FILES[0]).write_text("changed after binding\n", encoding="utf-8")
        return mapping

    harness.map_permission_dispatch_boundary = changed_map
    _response(monkeypatch, SCENARIOS)
    with pytest.raises(WhiteBoxBindingError, match="source digest changed after binding"):
        probe_w062_dispatch(harness)


def test_dispatch_probe_detects_missing_branch_even_if_executor_counts_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [dict(row) for row in SCENARIOS]
    rows[1]["outcome"] = "ok"
    _response(monkeypatch, rows)

    probe = probe_w062_dispatch(_harness(tmp_path))

    assert probe.unauthorized_executor_calls == 0
    assert "complete deny branch observation and permission cleanup" in probe.missing_for_full_case


def test_dispatch_probe_reports_unauthorized_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [dict(row) for row in SCENARIOS]
    rows[1]["order"] = [*rows[1]["order"], "executor"]
    _response(monkeypatch, rows)

    probe = probe_w062_dispatch(_harness(tmp_path))

    assert probe.unauthorized_executor_calls == 1
    assert "W062 executor call counts differ from expected metrics" in probe.missing_for_full_case


@pytest.mark.parametrize("rows", [[], SCENARIOS[:3], [{"name": name} for name in ["allow", "deny", "not_listed", "error"]]])
def test_dispatch_probe_rejects_missing_or_unbound_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]],
) -> None:
    _response(monkeypatch, rows)
    with pytest.raises(WhiteBoxBindingError):
        probe_w062_dispatch(_harness(tmp_path))


def test_dispatch_probe_rejects_invalid_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        probe_w062_dispatch(_harness(tmp_path), timeout=0)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required for the source probe")
def test_pinned_opencode_source_executes_real_dispatcher_with_four_branches() -> None:
    source = os.environ.get("OPENCODE_WHITEBOX_SOURCE")
    if not source:
        pytest.skip("Set OPENCODE_WHITEBOX_SOURCE to an existing pinned OpenCode checkout")
    observed = probe_w062_dispatch(OpenCodeWhiteBoxHarness(Path(source)))

    assert observed.binding.checkout_commit == observed.binding.tag_commit
    assert observed.allowed_executor_calls == 1
    assert observed.unauthorized_executor_calls == 0
    assert all(item["pending_after"] == 0 for item in observed.scenarios)
    assert observed.scenarios[0]["order"].index("permission.ended") < observed.scenarios[0]["order"].index("executor")
    assert [item["outcome"] for item in observed.scenarios] == [
        "ok", "DeniedError", "RejectedError", "TypeError",
    ]
    assert "instrumented full production runtime (isolated source bodies use fixture services)" in observed.missing_for_full_case
