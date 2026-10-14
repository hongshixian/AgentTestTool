"""Offline regression for the Codex driver: command shape, event parsing and assembly."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from agent_models.codex.driver import (
    CodexDriver, McpServer, TurnOutcome, child_environment, parse_events, permission_args,
)
from agent_models.codex.model import CodexAgentModel
from agent_models.codex.profile import CodexTestProfile
from agent_models.factory import AgentModelFactory
from agent_models.interaction import PermissionPolicy

posix_only = pytest.mark.skipif(os.name == "nt", reason="the fake CLI is a POSIX shebang script")


def _fake_cli(tmp_path: Path, stdout: str) -> Path:
    script = tmp_path / "codex"
    script.write_text(f"#!{sys.executable}\nprint({stdout!r})\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@pytest.fixture
def model_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    created: list[CodexAgentModel] = []

    def build(version_line: str | None) -> CodexAgentModel:
        executable = _fake_cli(tmp_path, version_line) if version_line else tmp_path / "missing" / "codex"
        monkeypatch.setenv("CODEX_BIN", str(executable))
        workspace = tmp_path / f"ws{len(created)}"
        workspace.mkdir()
        model = AgentModelFactory.create("codex", workspace=workspace, evidence_directory=tmp_path / f"ev{len(created)}")
        assert isinstance(model, CodexAgentModel)
        created.append(model)
        return model

    yield build
    for model in created:
        model.close()


@posix_only
def test_any_reported_version_is_accepted(model_factory) -> None:
    result = model_factory("codex-cli 0.160.0").check_installation()
    assert result.installed and "0.160.0" in result.detail


@posix_only
def test_unparseable_version_is_not_installed(model_factory) -> None:
    assert not model_factory("something else").check_installation().installed


def test_missing_executable(model_factory) -> None:
    model = model_factory(None)
    assert not model.check_installation().installed
    assert model.check_authentication().status.value == "error"


def test_factory_wiring() -> None:
    assert AgentModelFactory.parallel_block_reason("codex") is None
    with AgentModelFactory.worker_environment("codex") as environment:
        assert environment == {}


def test_profile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CODEX_BIN", "CODEX_TEST_MODEL", "CODEX_TEST_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    profile = CodexTestProfile.from_environment()
    assert (profile.executable, profile.model, profile.reasoning_effort) == ("codex", "gpt-6-luna", "high")


def test_permission_policies_map_to_sandbox_modes() -> None:
    assert 'sandbox_mode="read-only"' in permission_args(PermissionPolicy.DENY_UNAPPROVED, allow_tools=True)
    assert 'sandbox_mode="workspace-write"' in permission_args(PermissionPolicy.ALLOW_WORKSPACE_EDITS, allow_tools=True)
    assert permission_args(PermissionPolicy.BYPASS, allow_tools=True) == ["--dangerously-bypass-approvals-and-sandbox"]
    disabled = permission_args(PermissionPolicy.BYPASS, allow_tools=False)
    assert 'sandbox_mode="read-only"' in disabled and 'approval_policy="never"' in disabled


def test_child_environment_drops_harness_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "sk-judge-placeholder")
    monkeypatch.setenv("OPENCLAW_TEST_API_KEY", "sk-openclaw-placeholder")
    environment = child_environment(tmp_path / "codex")
    assert "JUDGE_API_KEY" not in environment and "OPENCLAW_TEST_API_KEY" not in environment
    assert str(tmp_path) in environment["PATH"]


def test_command_shapes(tmp_path: Path) -> None:
    driver = CodexDriver(CodexTestProfile(), executable=tmp_path / "codex", workspace=tmp_path)
    try:
        driver.mcp = McpServer(command="python3", args=("-u", "bridge.py"), enabled_tools=("lookup",))
        last = tmp_path / "last.txt"
        new = driver.command("-starts with a dash", session_id=None, policy=PermissionPolicy.DENY_UNAPPROVED,
                             allow_tools=True, ephemeral=True, last_message=last)
        assert new[:4] == [str(tmp_path / "codex"), "exec", "--color", "never"]
        assert new[-2:] == ["--", "-starts with a dash"] and "--ephemeral" in new
        assert "--cd" in new and 'shell_environment_policy.inherit="core"' in new
        assert 'mcp_servers.ats_mock.enabled_tools=["lookup"]' in new
        assert 'mcp_servers.ats_mock.default_tools_approval_mode="approve"' in new
        resumed = driver.command("next", session_id="thread-1", policy=PermissionPolicy.DENY_UNAPPROVED,
                                 allow_tools=False, ephemeral=False, last_message=last)
        assert resumed[4] == "resume" and resumed[-3:] == ["--", "thread-1", "next"]
        assert "--cd" not in resumed and "-s" not in resumed
        assert not any(arg.startswith("mcp_servers.") for arg in resumed)
    finally:
        driver.close()


def _events(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events)


def test_events_ignore_config_warning_items() -> None:
    outcome = TurnOutcome()
    parse_events(_events(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "item.completed", "item": {"type": "error", "message": "ignoring unrecognized setting"}},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "ls", "exit_code": 0,
                                            "status": "completed"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10}},
    ), outcome)
    assert outcome.ok and outcome.session_id == "t-1" and outcome.response == "done"
    assert outcome.tool_calls == [{"type": "command_execution", "command": "ls", "exit_code": 0, "status": "completed"}]


def test_events_failed_turn() -> None:
    outcome = TurnOutcome()
    parse_events(_events({"type": "thread.started", "thread_id": "t-2"},
                         {"type": "turn.failed", "error": {"message": "stream disconnected"}}), outcome)
    assert not outcome.ok and outcome.error == "stream disconnected"


def test_turn_result_mapping(model_factory) -> None:
    model = model_factory(None)
    timed_out = model._turn_result(TurnOutcome(timed_out=True, error="exceeded"), PermissionPolicy.DENY_UNAPPROVED, True)
    assert not timed_out.completed and timed_out.returncode == -1
    done = model._turn_result(TurnOutcome(session_id="t", response="ok", ok=True, returncode=0),
                              PermissionPolicy.BYPASS, True)
    assert done.completed and done.returncode == 0 and done.session_id == "t"
