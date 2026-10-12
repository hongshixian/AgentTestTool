"""Offline regression for the OpenClaw driver: permission mapping, envelope parsing and assembly."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from agent_models.factory import AgentModelFactory
from agent_models.interaction import PermissionPolicy
from agent_models.openclaw.driver import (
    OpenClawDriver, TurnOutcome, _base_environment, parse_envelope, tool_denials,
)
from agent_models.openclaw.model import OpenClawAgentModel
from agent_models.openclaw.profile import OpenClawTestProfile

posix_only = pytest.mark.skipif(os.name == "nt", reason="the fake CLI is a POSIX shebang script")


def _fake_cli(tmp_path: Path, version: str) -> Path:
    script = tmp_path / "openclaw"
    script.write_text(f"#!{sys.executable}\nprint('\\x1b[1mOpenClaw {version} (713ba57)\\x1b[0m')\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@pytest.fixture
def model_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    created: list[OpenClawAgentModel] = []

    def build(version: str | None, *, api_key: str = "sk-test-placeholder") -> OpenClawAgentModel:
        executable = _fake_cli(tmp_path, version) if version else tmp_path / "missing" / "openclaw"
        monkeypatch.setenv("OPENCLAW_BIN", str(executable))
        monkeypatch.setenv("OPENCLAW_TEST_API_KEY", api_key)
        workspace = tmp_path / f"ws{len(created)}"
        workspace.mkdir()
        model = AgentModelFactory.create("openclaw", workspace=workspace,
                                         evidence_directory=tmp_path / f"ev{len(created)}")
        assert isinstance(model, OpenClawAgentModel)
        created.append(model)
        return model

    yield build
    for model in created:
        model.close()


@posix_only
def test_pinned_version_is_installed(model_factory) -> None:
    result = model_factory("2026.8.35").check_installation()
    assert result.installed and "2026.8.35" in result.detail


@posix_only
def test_other_version_is_not_accepted(model_factory) -> None:
    result = model_factory("2026.10.1").check_installation()
    assert not result.installed and "2026.8.35 is required" in result.detail


def test_missing_executable(model_factory) -> None:
    model = model_factory(None)
    assert not model.check_installation().installed
    assert model.check_authentication().status.value == "error"


def test_factory_declares_private_worker_state() -> None:
    assert AgentModelFactory.parallel_block_reason("openclaw") is None
    with AgentModelFactory.worker_environment("openclaw") as environment:
        assert environment == {}


def test_api_key_is_redacted_from_evidence(model_factory) -> None:
    model = model_factory(None, api_key="sk-unique-openclaw-probe")
    assert "sk-unique-openclaw-probe" not in str(model.environment.ledger.redact("key sk-unique-openclaw-probe"))


def test_permission_policies_map_to_config_denials() -> None:
    assert tool_denials(PermissionPolicy.DENY_UNAPPROVED, allow_tools=False) == ["*"]
    deny = tool_denials(PermissionPolicy.DENY_UNAPPROVED, allow_tools=True)
    assert {"group:runtime", "write", "edit", "apply_patch"} <= set(deny) and "read" not in deny
    edits = tool_denials(PermissionPolicy.ALLOW_WORKSPACE_EDITS, allow_tools=True)
    assert "group:runtime" in edits and "write" not in edits
    bypass = tool_denials(PermissionPolicy.BYPASS, allow_tools=True, hidden_mock_tools=frozenset({"secret"}))
    assert "group:runtime" not in bypass and "ats_mock__secret" in bypass


def test_child_environment_does_not_inherit_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "sk-judge-placeholder")
    monkeypatch.setenv("OPENCLAW_TEST_API_KEY", "sk-openclaw-placeholder")
    environment = _base_environment(tmp_path / "openclaw")
    assert "JUDGE_API_KEY" not in environment and "OPENCLAW_TEST_API_KEY" not in environment
    assert str(tmp_path) in environment["PATH"]


def test_private_config_is_owner_only_and_confines_workspace(tmp_path: Path) -> None:
    profile = OpenClawTestProfile(api_key="sk-config-placeholder")
    driver = OpenClawDriver(profile, executable=tmp_path / "openclaw", workspace=tmp_path)
    try:
        driver._write_config(driver._config(PermissionPolicy.ALLOW_WORKSPACE_EDITS, True, frozenset()))
        if os.name != "nt":
            assert stat.S_IMODE(driver.config_path.stat().st_mode) == 0o600
        config = json.loads(driver.config_path.read_text())
        assert config["tools"]["fs"]["workspaceOnly"] is True
        assert config["agents"]["defaults"]["workspace"] == str(tmp_path.resolve())
        assert config["agents"]["defaults"]["skipBootstrap"] is True
        assert "mcp" not in config
    finally:
        driver.close()
    assert not driver.config_path.exists()


def test_envelope_success_and_errors() -> None:
    outcome = TurnOutcome("s", returncode=0)
    parse_envelope(json.dumps({"payloads": [{"text": "a"}, {"text": "b"}], "meta": {
        "aborted": False, "agentMeta": {"sessionId": "s", "terminalReceipt": {"successfulToolNames": ["write"]}}}}),
        outcome)
    assert outcome.ok and outcome.response == "a\n\nb" and outcome.tool_names == ("write",)

    failed = TurnOutcome("s", returncode=1)
    parse_envelope(json.dumps({"ok": False, "error": {"type": "cli_error", "message": "HTTP 401"}}), failed)
    assert not failed.ok and failed.error == "HTTP 401"

    aborted = TurnOutcome("s", returncode=0)
    parse_envelope(json.dumps({"payloads": [], "meta": {"aborted": True}}), aborted)
    assert not aborted.ok and "aborted" in aborted.error

    garbage = TurnOutcome("s", returncode=0)
    parse_envelope("not json", garbage)
    assert not garbage.ok and "JSON" in garbage.error


def test_turn_result_maps_timeouts(model_factory) -> None:
    model = model_factory(None)
    timed_out = model._turn_result(TurnOutcome("s", timed_out=True, error="exceeded"),
                                   PermissionPolicy.DENY_UNAPPROVED, True)
    assert not timed_out.completed and timed_out.returncode == -1
    finished = model._turn_result(TurnOutcome("s", response="ok", ok=True, returncode=0),
                                  PermissionPolicy.BYPASS, True)
    assert finished.completed and finished.returncode == 0 and finished.response == "ok"
