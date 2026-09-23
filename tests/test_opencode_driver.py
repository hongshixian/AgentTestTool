"""Offline OpenCode CLI and JSON event contract tests."""

import json
import subprocess
from pathlib import Path

import pytest

from agent_models.interaction import PermissionPolicy
from agent_models.opencode.driver import OpenCodeDriver
from agent_models.opencode.profile import OpenCodeTestProfile
from agent_models.processes import ProcessCleanupError
from agent_models.result import AuthStatus


def _profile(tmp_path: Path) -> OpenCodeTestProfile:
    key = tmp_path / "key.txt"
    key.write_text("fake-provider-key", encoding="utf-8")
    config = tmp_path / "test-provider.json"
    config.write_text(json.dumps({
        "provider": {"iiis": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "https://example.invalid/v1", "apiKey": "{file:" + str(key) + "}"},
            "models": {"infi/deepseek-v4.1-flash": {"name": "Test"}},
        }},
    }), encoding="utf-8")
    return OpenCodeTestProfile(source=config)


def _events(text: str, session_id: str = "ses-test") -> str:
    return "\n".join(json.dumps(value) for value in (
        {"type": "step_start", "sessionID": session_id, "part": {"type": "step-start"}},
        {"type": "text", "sessionID": session_id, "part": {"type": "text", "text": text}},
        {"type": "step_finish", "sessionID": session_id, "part": {"type": "step-finish", "reason": "stop"}},
    ))


def test_json_terminal_result_and_session_id() -> None:
    result = OpenCodeDriver.parse_output(_events("OK"), duration_seconds=1.0)
    assert result.response == "OK"
    assert result.session_id == "ses-test"
    assert result.completed
    assert result.duration_seconds == 1.0


@pytest.mark.parametrize("raw,expected", [
    ('not json\n' + _events("OK"), False),
    (json.dumps({"type": "text", "part": {"type": "text", "text": "partial"}}), False),
    (_events(""), False),
    (_events("OK") + '\n' + json.dumps({"type": "error"}), False),
])
def test_incomplete_events_do_not_claim_completion(raw: str, expected: bool) -> None:
    assert OpenCodeDriver.parse_output(raw).completed is expected


def test_authentication_checks_real_model_not_auth_file(monkeypatch, tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    try:
        observed: list[tuple[str, ...]] = []

        def fake_run(command, **kwargs):
            observed.append(tuple(command))
            assert kwargs["env"]["XDG_CONFIG_HOME"].startswith(str(profile.root))
            assert kwargs["env"]["OPENCODE_CONFIG_CONTENT"]
            assert kwargs["cwd"] == tmp_path
            assert kwargs["capture_output"] is True
            assert kwargs["timeout"] == 60.0
            return subprocess.CompletedProcess(command, 0, _events("AUTH_OK"), "")

        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        monkeypatch.setattr("agent_models.opencode.driver.shutil.which", lambda name: "/bin/opencode")
        driver = OpenCodeDriver(workspace=tmp_path, profile=profile)
        assert driver.check_authentication().status is AuthStatus.AUTHENTICATED
        assert "--model" in observed[0]
        assert "iiis/infi/deepseek-v4.1-flash" in observed[0]
        assert "--auto" not in observed[0]
    finally:
        profile.close()


def test_permissions_are_independent_from_tools(monkeypatch, tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    try:
        permissions = []
        def fake_run(command, **kwargs):
            permissions.append(json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])["permission"])
            return subprocess.CompletedProcess(command, 0, _events("OK"), "")
        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        driver = OpenCodeDriver(workspace=tmp_path, profile=profile)
        driver.send_prompt("probe", allow_tools=True)
        driver.send_prompt("probe", allow_tools=True, permission_policy=PermissionPolicy.ALLOW_WORKSPACE_EDITS)
        assert permissions[0]["*"] == "deny" and "edit" not in permissions[0]
        assert permissions[1]["edit"] == "allow"
        with pytest.raises(ValueError, match="permission requests"):
            driver.send_prompt("probe", permission_policy=PermissionPolicy.ASK)
    finally:
        profile.close()


def test_disabling_tools_overrides_configured_mcp_even_under_bypass(monkeypatch, tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    try:
        profile.configure_mcp(
            {"ats_mock": {"type": "local", "command": ["python", "mock.py"]}},
            tools={"ats_mock_*": True, "read": True},
        )
        observations = []

        def fake_run(command, **kwargs):
            observations.append((tuple(command), json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])))
            return subprocess.CompletedProcess(command, 0, _events("OK"), "")

        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        driver = OpenCodeDriver(workspace=tmp_path, profile=profile)
        assert driver.send_prompt(
            "no tools", allow_tools=False, permission_policy=PermissionPolicy.BYPASS,
        ).completed
        assert driver.send_prompt("tools allowed", allow_tools=True, has_mock=True).completed
        command, config = observations[0]
        assert "--auto" not in command
        assert config["permission"] == {"*": "deny"}
        assert config["tools"] == {"*": False, "ats_mock_*": False, "read": False}
        assert "tools" not in observations[1][1]
        saved = json.loads(profile.config_file.read_text(encoding="utf-8"))
        assert saved["mcp"]["ats_mock"]["type"] == "local"
        assert saved["tools"] == {"ats_mock_*": True, "read": True}
    finally:
        profile.close()


@pytest.mark.parametrize("events,fallback", [
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-B", "part": {"reason": "stop"}},
    ], None),
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "stop", "sessionID": "ses-B"}},
    ], None),
    ([
        {"type": "text", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "stop"}},
    ], None),
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "part": {"reason": "stop"}},
    ], None),
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "stop"}},
    ], "ses-B"),
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"type": "text", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "stop"}},
        {"type": "error", "sessionID": "ses-B", "error": {"name": "Failed"}},
    ], None),
    ([
        {"type": "text", "sessionID": "ses-A", "part": {"sessionID": "", "text": "A"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "stop"}},
    ], None),
])
def test_mixed_or_missing_sessions_never_complete(events, fallback: str | None) -> None:
    output = "\n".join(json.dumps(event) for event in events)
    result = OpenCodeDriver.parse_output(output, fallback_session_id=fallback)
    assert not result.completed
    assert not result.response
    assert result.stderr


def test_nested_session_id_without_outer_id_is_valid() -> None:
    result = OpenCodeDriver.parse_output("\n".join(json.dumps(event) for event in (
        {"type": "text", "part": {"type": "text", "sessionID": "ses-A", "text": "OK"}},
        {"type": "step_finish", "part": {"sessionID": "ses-A", "reason": "stop"}},
    )))
    assert result.completed
    assert result.session_id == "ses-A"


def test_intermediate_step_finish_is_not_a_terminal_response() -> None:
    result = OpenCodeDriver.parse_output("\n".join(json.dumps(event) for event in (
        {"type": "text", "sessionID": "ses-A", "part": {"text": "working"}},
        {"type": "step_finish", "sessionID": "ses-A", "part": {"reason": "tool-calls"}},
    )))
    assert not result.completed


def test_one_shot_timeout_returns_incomplete_turn_only_after_managed_cleanup(
    monkeypatch, tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    try:
        def fake_run(command, **kwargs):
            assert kwargs["timeout"] == 1.25
            assert kwargs["env"]["OPENCODE_CONFIG_DIR"].startswith(str(profile.root))
            assert kwargs["text"] is True
            assert kwargs["encoding"] == "utf-8"
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=profile.secret)

        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        result = OpenCodeDriver(workspace=tmp_path, profile=profile).send_prompt(
            "probe", timeout=1.25,
        )
        assert not result.completed
        assert result.returncode == -1
        assert result.stderr == "OpenCode turn timed out"
        assert result.raw_output == ""
        assert profile.secret not in str(result)
    finally:
        profile.close()


def test_cleanup_error_is_not_reported_as_safe_timeout(monkeypatch, tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    try:
        def fake_run(command, **kwargs):
            raise ProcessCleanupError("Cannot confirm worker process tree termination")

        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        with pytest.raises(ProcessCleanupError, match="Cannot confirm worker process tree termination"):
            OpenCodeDriver(workspace=tmp_path, profile=profile).send_prompt("probe", timeout=0.1)
    finally:
        profile.close()


def test_one_shot_redacts_secret_from_stdout_and_stderr(monkeypatch, tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    try:
        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(
                command, 0, _events("OK " + profile.secret), "upstream: " + profile.secret,
            )

        monkeypatch.setattr("agent_models.opencode.driver.run_managed_process", fake_run)
        result = OpenCodeDriver(workspace=tmp_path, profile=profile).send_prompt("probe")
        assert result.completed
        assert profile.secret not in result.response
        assert profile.secret not in result.raw_output
        assert profile.secret not in result.stderr
    finally:
        profile.close()
