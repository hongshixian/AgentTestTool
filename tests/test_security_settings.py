"""Verify security test target settings."""

from __future__ import annotations

import pytest

from test_cases.security import (
    DEFAULT_UNTRUSTED_INSTANCE_ID,
    DEFAULT_UNTRUSTED_USER_ID,
    SecurityIdentitySettings,
    SecurityTargetSettings,
)


class TestSecuritySettings:
    def test_prompt_injection_only_requires_real_account_b_identifiers(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("AGENT_TEST_B_USER_ID", "real-user-b")
        monkeypatch.setenv("AGENT_TEST_B_INSTANCE_ID", "real-instance-b")
        monkeypatch.delenv("AGENT_TEST_A_USER_ID", raising=False)
        monkeypatch.delenv("AGENT_TEST_A_INSTANCE_ID", raising=False)

        settings = SecurityTargetSettings.from_environment()

        assert settings.b_user_id == "real-user-b"
        assert settings.b_instance_id == "real-instance-b"

    def test_prompt_injection_uses_untrusted_targets_without_account_b(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.delenv("AGENT_TEST_B_USER_ID", raising=False)
        monkeypatch.delenv("AGENT_TEST_B_INSTANCE_ID", raising=False)

        settings = SecurityTargetSettings.from_environment()

        assert settings.b_user_id == DEFAULT_UNTRUSTED_USER_ID
        assert settings.b_instance_id == DEFAULT_UNTRUSTED_INSTANCE_ID

    def test_context_scenarios_require_both_real_account_identities(
        self,
        monkeypatch,
    ) -> None:
        for name in (
            "AGENT_TEST_A_USER_ID",
            "AGENT_TEST_A_INSTANCE_ID",
            "AGENT_TEST_B_USER_ID",
            "AGENT_TEST_B_INSTANCE_ID",
        ):
            monkeypatch.delenv(name, raising=False)

        with pytest.raises(ValueError, match="AGENT_TEST_A_USER_ID"):
            SecurityIdentitySettings.from_environment()
