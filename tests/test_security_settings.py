"""Verify security test target settings."""

from __future__ import annotations

import pytest

from test_cases.security import (
    SecurityIdentitySettings,
    SecurityTargetSettings,
)


class TestSecuritySettings:
    def test_target_settings_accept_explicit_real_account_b_identifiers(
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

    @pytest.mark.parametrize("configured_value", [None, "", "   "])
    def test_target_settings_reject_missing_account_b_instead_of_using_fake_ids(
        self,
        monkeypatch,
        configured_value: str | None,
    ) -> None:
        for name in ("AGENT_TEST_B_USER_ID", "AGENT_TEST_B_INSTANCE_ID"):
            if configured_value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, configured_value)

        with pytest.raises(ValueError, match="AGENT_TEST_B_USER_ID"):
            SecurityTargetSettings.from_environment()

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
