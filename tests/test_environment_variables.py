"""Verify test-only secrets stay outside the target process environment."""

import os
from pathlib import Path
import subprocess

from agent_models.codebuddy.driver import CodeBuddyDriver
from configs.environment import agent_process_environment, sensitive_environment_values


def test_driver_does_not_inherit_judge_or_orchestration_variables(tmp_path, monkeypatch):
    fake_environment = {
        "JUDGE_API_KEY": "fake-judge-key-not-valid",
        "JUDGE_API_URL": "https://judge.invalid",
        "AGENT_TEST_TEST_SECRET": "fake-test-secret-not-valid",
        "AGENT_TEST_RUN_ID": "test-run",
        "CODEBUDDY_API_KEY": "fake-product-key-not-valid",
        "PATH": "/test-only/bin",
    }
    monkeypatch.setattr(os, "environ", fake_environment)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    response = CodeBuddyDriver(workspace=tmp_path).send_prompt("test")
    assert response.raw_output == "ok"
    assert calls[0][1]["encoding"] == "utf-8"
    assert calls[0][1]["errors"] == "replace"
    child = calls[0][1]["env"]
    assert "JUDGE_API_KEY" not in child
    assert "JUDGE_API_URL" not in child
    assert "AGENT_TEST_TEST_SECRET" not in child
    assert "AGENT_TEST_RUN_ID" not in child
    assert child["CODEBUDDY_API_KEY"] == fake_environment["CODEBUDDY_API_KEY"]
    assert child["PATH"] == fake_environment["PATH"]
    assert fake_environment["JUDGE_API_KEY"] == "fake-judge-key-not-valid"


def test_sensitive_values_collect_named_credentials_without_duplicates():
    environment = {
        "API_KEY": "fake-api-key",
        "JUDGE_API_KEY": "fake-api-key",
        "ACCESS_TOKEN": "fake-access-token",
        "PASSWORD": "fake-password",
        "SERVICE_PASSWORD": "fake-service-password",
        "client_secret": "fake-client-secret",
        "AWS_SECRET_ACCESS_KEY": "fake-aws-secret",
        "TOKEN": "fake-token",
        "SERVICE_TOKEN": "  fake-exact-token  ",
        "EMPTY_TOKEN": "",
        "BLANK_SECRET": "  \t ",
        "JUDGE_MODEL_NAME": "test-model",
        "TOKENIZER_PATH": "test-tokenizer-path",
        "SECRETARY": "ordinary-name",
        "PATH": "/fake/bin",
    }
    assert sensitive_environment_values(environment) == (
        "fake-api-key", "fake-access-token", "fake-password", "fake-service-password",
        "fake-client-secret", "fake-aws-secret", "fake-token", "  fake-exact-token  ",
    )
    assert environment["SERVICE_TOKEN"] == "  fake-exact-token  "


def test_empty_explicit_mapping_does_not_fall_back_to_process_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", {"TOKEN": "fake-process-token", "PATH": "/fake/bin"})
    assert sensitive_environment_values({}) == ()
    assert agent_process_environment({}) == {}
    assert sensitive_environment_values() == ("fake-process-token",)
    assert agent_process_environment() == {"TOKEN": "fake-process-token", "PATH": "/fake/bin"}


def test_environment_filter_is_case_insensitive_and_retains_product_auth():
    environment = {
        "judge_api_key": "fake-judge-key",
        "AGENT_TEST_RUN_ID": "test-run",
        "agent_test_mock_secret": "fake-test-secret",
        "CODEBUDDY_API_KEY": "fake-codebuddy-key",
        "CODEBUDDY_CONFIG_DIR": "/fake/config",
        "HTTPS_PROXY": "http://proxy.invalid",
        "PATH": "/fake/bin",
        "SYSTEMROOT": "C:/FakeWindows",
        "HOME": "/fake/user",
        "LANG": "C.UTF-8",
        "OTHER_SECRET": "fake-retained-secret",
    }
    filtered = agent_process_environment(environment)
    assert set(filtered) == {
        "CODEBUDDY_API_KEY", "CODEBUDDY_CONFIG_DIR", "HTTPS_PROXY", "PATH",
        "SYSTEMROOT", "HOME", "LANG", "OTHER_SECRET",
    }
    filtered["PATH"] = "changed-copy"
    assert environment["PATH"] == "/fake/bin"
    assert "judge_api_key" in environment


def test_helpers_do_not_read_configuration_files(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Configuration file access is forbidden for these helpers")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    assert sensitive_environment_values({"TOKEN": "fake-token"}) == ("fake-token",)
    assert agent_process_environment({"JUDGE_API_KEY": "fake-key", "PATH": "/fake/bin"}) == {"PATH": "/fake/bin"}


def test_driver_retains_explicit_product_config_and_permission_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {"JUDGE_API_KEY": "fake-judge-key", "CODEBUDDY_API_KEY": "fake-product-key"})
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    config = tmp_path / "fake-product-config"
    driver = CodeBuddyDriver(workspace=tmp_path, config_dir=config)
    driver.send_prompt("test", allow_tools=True)
    command, options = calls[0]
    assert "--dangerously-skip-permissions" in command
    assert options["env"] == {
        "CODEBUDDY_API_KEY": "fake-product-key",
        "CODEBUDDY_CONFIG_DIR": str(config),
        "CODEBUDDY_IS_SANDBOX": "1",
    }
    driver.send_prompt("test", allow_tools=False)
    assert "--dangerously-skip-permissions" not in calls[1][0]
    assert "CODEBUDDY_IS_SANDBOX" not in calls[1][1]["env"]
