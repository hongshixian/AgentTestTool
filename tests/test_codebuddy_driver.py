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
        observed_command: list[str] = []

        def fake_run(command, **kwargs):
            observed_command.extend(command)
            observed_environment.update(kwargs["env"])
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)

        driver.send_prompt("test")

        assert observed_environment["CODEBUDDY_CONFIG_DIR"] == str(tmp_path)
        model_index = observed_command.index("--model") + 1
        assert observed_command[model_index] == "hy3"

    def test_explicit_model_argument_overrides_the_default(
        self, monkeypatch, tmp_path
    ) -> None:
        observed_command: list[str] = []

        def fake_run(command, **_kwargs):
            observed_command.extend(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        driver = CodeBuddyDriver(workspace=tmp_path)

        driver.send_prompt("test", extra_args=("--model", "hy3-x"))

        assert observed_command.count("--model") == 1
        assert observed_command[observed_command.index("--model") + 1] == "hy3-x"

    def test_applies_collector_environment_to_every_managed_cli_launch(
        self, monkeypatch, tmp_path
    ) -> None:
        environments: list[dict[str, str]] = []
        commands: list[list[str]] = []

        def fake_run(command, **kwargs):
            commands.append(list(command))
            environments.append(dict(kwargs["env"]))
            if "--bg" in command:
                return subprocess.CompletedProcess(
                    command, 0, "Backgrounded · task-1", ""
                )
            if "agents" in command:
                return subprocess.CompletedProcess(command, 0, "[]", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        driver = CodeBuddyDriver(
            workspace=tmp_path,
            config_dir=tmp_path,
            process_environment_overrides={
                "HTTPS_PROXY": "http://127.0.0.1:43123",
                "NODE_EXTRA_CA_CERTS": str(tmp_path / "ca.pem"),
            },
        )

        driver.send_prompt("test")
        driver.start_background_task("test", name="task")

        assert len(environments) == 3
        assert all(
            environment["HTTPS_PROXY"] == "http://127.0.0.1:43123"
            and environment["NODE_EXTRA_CA_CERTS"] == str(tmp_path / "ca.pem")
            and environment["CODEBUDDY_CONFIG_DIR"] == str(tmp_path)
            for environment in environments
        )
        model_commands = [command for command in commands if "--print" in command or "--bg" in command]
        assert len(model_commands) == 2
        assert all(
            command[command.index("--model") + 1] == "hy3"
            for command in model_commands
        )

    def test_applies_collector_environment_to_interactive_session(
        self, monkeypatch, tmp_path
    ) -> None:
        observed: dict[str, object] = {}

        class FakeSession:
            def __init__(self, **kwargs):
                observed["environment"] = kwargs["environment"]
                observed["command"] = kwargs["command"]

        monkeypatch.setattr(
            "agent_models.codebuddy.driver.CodeBuddyInteractiveSession",
            FakeSession,
        )
        driver = CodeBuddyDriver(
            workspace=tmp_path,
            config_dir=tmp_path,
            process_environment_overrides={
                "HTTPS_PROXY": "http://127.0.0.1:43123",
                "NODE_EXTRA_CA_CERTS": str(tmp_path / "ca.pem"),
            },
        )

        driver.start_session(session_id="session-1")

        environment = observed["environment"]
        assert isinstance(environment, dict)
        assert environment["HTTPS_PROXY"] == "http://127.0.0.1:43123"
        assert environment["NODE_EXTRA_CA_CERTS"] == str(tmp_path / "ca.pem")
        assert environment["CODEBUDDY_CONFIG_DIR"] == str(tmp_path)
        command = observed["command"]
        assert isinstance(command, list)
        assert command[command.index("--model") + 1] == "hy3"

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

    def test_close_ignores_project_directory_disappearing_during_scan(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        tmp_path.joinpath("projects").mkdir()

        def disappearing_walk(_root, *, onerror, **_kwargs):
            onerror(FileNotFoundError("project directory disappeared"))
            return iter(())

        monkeypatch.setattr("agent_models.codebuddy.driver.os.walk", disappearing_walk)
        driver = CodeBuddyDriver(workspace=tmp_path, config_dir=tmp_path)

        driver.close(session_id="ats-session")
