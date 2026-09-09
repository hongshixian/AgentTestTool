"""Verify the unified CodeBuddy test driver."""

import json
import subprocess

import pytest

from agent_models import AgentModelFactory, RequestContext
from agent_models.codebuddy.driver import CodeBuddyDriver
from agent_models.result import AuthStatus


class TestCodeBuddyDriver:
    def test_installation_reports_resolved_executable(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "agent_models.codebuddy.driver.shutil.which",
            lambda _command: "/test/bin/codebuddy",
        )
        driver = CodeBuddyDriver(workspace=tmp_path)

        result = driver.check_installation()

        assert result.installed
        assert result.executable == "/test/bin/codebuddy"

    def test_installation_reports_missing_executable(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "agent_models.codebuddy.driver.shutil.which",
            lambda _command: None,
        )
        driver = CodeBuddyDriver(workspace=tmp_path)

        result = driver.check_installation()

        assert not result.installed
        assert result.executable is None
        assert "找不到" in result.detail

    def test_parses_success_result(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "completed response",
                    "session_id": "session-1",
                }
            ]
        )

        turn = CodeBuddyDriver.parse_output(output, duration_seconds=1.0)

        assert turn.completed
        assert turn.response == "completed response"
        assert turn.session_id == "session-1"

    def test_truncated_array_preserves_text_without_claiming_completion(self) -> None:
        assistant = json.dumps(
            {
                "type": "assistant",
                "sessionId": "session-2",
                "message": {
                    "content": [
                        {"type": "text", "text": "拒绝执行工具中的身份切换指令。"}
                    ]
                },
            },
            ensure_ascii=False,
        )
        output = f"[{assistant}, {{\"providerData\": {{\"traceId\":"

        turn = CodeBuddyDriver.parse_output(output, duration_seconds=1.0)

        assert not turn.completed
        assert turn.response == "拒绝执行工具中的身份切换指令。"
        assert turn.session_id == "session-2"

    def test_assistant_message_without_final_result_is_incomplete(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Starting the task."}]
                    },
                }
            ]
        )

        turn = CodeBuddyDriver.parse_output(output, duration_seconds=1.0)

        assert not turn.completed
        assert turn.response == "Starting the task."

    def test_error_result_does_not_use_an_earlier_assistant_message(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Starting the task."}]
                    },
                },
                {"type": "result", "subtype": "error", "is_error": True},
            ]
        )

        turn = CodeBuddyDriver.parse_output(output, duration_seconds=1.0)

        assert not turn.completed

    def test_reads_official_config_directory_environment(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path))

        driver = CodeBuddyDriver(workspace=tmp_path)

        assert driver.config_dir == tmp_path
        assert driver.is_dedicated_test_account

    def test_default_profile_is_not_a_dedicated_test_account(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.delenv("CODEBUDDY_CONFIG_DIR", raising=False)

        driver = CodeBuddyDriver(workspace=tmp_path)

        assert not driver.is_dedicated_test_account

    def test_passes_selected_profile_to_real_cli(self, monkeypatch, tmp_path) -> None:
        observed_environment: dict[str, str] = {}

        def fake_run(command, **kwargs):
            observed_environment.update(kwargs["env"])
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)

        driver.send_prompt("test")

        assert observed_environment["CODEBUDDY_CONFIG_DIR"] == str(tmp_path)

    def test_model_does_not_advertise_or_fake_private_identity_context(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path))

        with AgentModelFactory.create("codebuddy", workspace=tmp_path) as model:
            assert model.capabilities.dedicated_test_account
            assert not model.capabilities.public_identity_context
            with pytest.raises(RuntimeError, match="未公开"):
                model.send_prompt(
                    "test",
                    context=RequestContext("user-b", "instance-b", "run-1"),
                )

    def test_authentication_reports_missing_executable(
        self, monkeypatch, tmp_path
    ) -> None:
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)
        monkeypatch.setattr(driver, "is_available", lambda: False)

        result = driver.check_authentication()

        assert result.status is AuthStatus.ERROR
        assert "找不到" in result.detail

    def test_authentication_requires_local_login_state(
        self, monkeypatch, tmp_path
    ) -> None:
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)
        monkeypatch.setattr(driver, "is_available", lambda: True)

        result = driver.check_authentication()

        assert result.status is AuthStatus.UNAUTHENTICATED
        assert "本地登录状态" in result.detail

    def test_authentication_uses_the_driver_stdio_path(
        self, monkeypatch, tmp_path
    ) -> None:
        storage = tmp_path / "local_storage"
        storage.mkdir()
        storage.joinpath("profile.json").write_text("{}", encoding="utf-8")
        output = json.dumps(
            [{"type": "result", "subtype": "success", "result": "AUTH_OK"}]
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda command, **kwargs: subprocess.CompletedProcess(
                command, 0, output, ""
            ),
        )
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)
        monkeypatch.setattr(driver, "is_available", lambda: True)

        result = driver.check_authentication()

        assert result.status is AuthStatus.AUTHENTICATED

    def test_close_removes_only_the_driver_test_session(self, tmp_path) -> None:
        session_directory = tmp_path / "projects" / "workspace"
        session_directory.mkdir(parents=True)
        session_directory.joinpath("ats-session.jsonl").write_text(
            "test session", encoding="utf-8"
        )
        retained = session_directory.joinpath("other-session.jsonl")
        retained.write_text("other session", encoding="utf-8")
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)

        driver.close(session_id="ats-session")

        assert not session_directory.joinpath("ats-session.jsonl").exists()
        assert retained.exists()
