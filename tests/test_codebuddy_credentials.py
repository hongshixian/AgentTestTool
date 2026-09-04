"""Verify selection of real CodeBuddy account profiles."""

from __future__ import annotations

import subprocess

import pytest

from agent_models import AgentModelFactory, RequestContext
from agent_models.codebuddy.credentials import CodeBuddyCredentialProvider
from agent_models.codebuddy.transport import CodeBuddyStdioTransport


class TestCodeBuddyCredentialProvider:
    def test_reads_official_config_directory_environment(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path))

        provider = CodeBuddyCredentialProvider()

        assert provider.config_dir == tmp_path
        assert provider.is_dedicated_test_account

    def test_default_profile_is_not_a_dedicated_test_account(self, monkeypatch) -> None:
        monkeypatch.delenv("CODEBUDDY_CONFIG_DIR", raising=False)

        provider = CodeBuddyCredentialProvider()

        assert not provider.is_dedicated_test_account

    def test_transport_passes_selected_profile_to_real_cli(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        observed_environment: dict[str, str] = {}

        def fake_run(command, **kwargs):
            observed_environment.update(kwargs["env"])
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        transport = CodeBuddyStdioTransport(workspace=tmp_path, config_dir=tmp_path)

        transport.request("test")

        assert observed_environment["CODEBUDDY_CONFIG_DIR"] == str(tmp_path)

    def test_model_does_not_advertise_or_fake_private_identity_context(
        self,
        monkeypatch,
        tmp_path,
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
