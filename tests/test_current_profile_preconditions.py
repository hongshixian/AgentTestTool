"""Verify injection scenarios require complete observation and real identities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models.result import AuthResult, AuthStatus
from test_cases.scenarios.natural_language_identity_override import (
    PROMPT_VARIANTS,
    NaturalLanguageIdentityScenarioRunner,
)
from test_cases.scenarios.tool_result_identity_injection import (
    AUTHORIZATION_MARKER,
    PRIVATE_MARKER,
    VARIANTS,
    ToolResultIdentityScenarioRunner,
)
from test_cases.security import SecurityIdentitySettings


class _ExecutionReached(RuntimeError):
    pass


class _AuthenticatedCurrentProfileAgent:
    def __init__(
        self, *, mock_tools: bool = False, security_boundary_observation: bool = True
    ) -> None:
        self.capabilities = SimpleNamespace(
            multi_turn=True,
            mock_tools=mock_tools,
            dedicated_test_account=False,
            security_boundary_observation=security_boundary_observation,
            external_observation=True,
        )
        self.mock_tool_configured = False
        self.authentication_checked = False

    def check_authentication(self) -> AuthResult:
        self.authentication_checked = True
        return AuthResult(AuthStatus.AUTHENTICATED, "current profile is authenticated")

    def configure_mock_tool(self, profile, *, run_id: str) -> None:
        self.mock_tool_configured = True

    def send_prompt(self, prompt: str, **kwargs):
        raise _ExecutionReached


class TestCurrentProfilePreconditions:
    @pytest.mark.parametrize("is_tool_injection", [False, True])
    def test_missing_complete_observation_skips_before_authentication_or_execution(
        self,
        is_tool_injection: bool,
    ) -> None:
        agent = _AuthenticatedCurrentProfileAgent(
            mock_tools=is_tool_injection,
            security_boundary_observation=False,
        )

        with pytest.raises(pytest.skip.Exception, match="完整|安全边界"):
            _run_scenario(agent, is_tool_injection=is_tool_injection)

        assert not agent.authentication_checked
        assert not agent.mock_tool_configured

    @pytest.mark.parametrize("is_tool_injection", [False, True])
    def test_missing_real_target_skips_without_fake_identifier_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        is_tool_injection: bool,
    ) -> None:
        monkeypatch.setenv("AGENT_TEST_A_USER_ID", "real-user-a")
        monkeypatch.setenv("AGENT_TEST_A_INSTANCE_ID", "real-instance-a")
        monkeypatch.delenv("AGENT_TEST_B_USER_ID", raising=False)
        monkeypatch.delenv("AGENT_TEST_B_INSTANCE_ID", raising=False)
        agent = _AuthenticatedCurrentProfileAgent(mock_tools=is_tool_injection)

        with pytest.raises(pytest.skip.Exception, match="AGENT_TEST_B_USER_ID"):
            _run_scenario(agent, is_tool_injection=is_tool_injection)

        assert not agent.authentication_checked
        assert not agent.mock_tool_configured

    @pytest.mark.parametrize("is_tool_injection", [False, True])
    def test_missing_real_account_a_identity_skips_before_execution(
        self,
        monkeypatch: pytest.MonkeyPatch,
        is_tool_injection: bool,
    ) -> None:
        monkeypatch.delenv("AGENT_TEST_A_USER_ID", raising=False)
        monkeypatch.delenv("AGENT_TEST_A_INSTANCE_ID", raising=False)
        monkeypatch.setenv("AGENT_TEST_B_USER_ID", "real-user-b")
        monkeypatch.setenv("AGENT_TEST_B_INSTANCE_ID", "real-instance-b")
        agent = _AuthenticatedCurrentProfileAgent(mock_tools=is_tool_injection)

        with pytest.raises(pytest.skip.Exception, match="AGENT_TEST_A_USER_ID"):
            _run_scenario(agent, is_tool_injection=is_tool_injection)

        assert not agent.authentication_checked
        assert not agent.mock_tool_configured

    @pytest.mark.parametrize("variant", VARIANTS, ids=lambda item: item.prompt_id)
    def test_tool_payload_contains_reviewed_identifiers_and_markers(self, variant) -> None:
        settings = SecurityIdentitySettings(
            "real-user-a", "real-instance-a", "real-user-b", "real-instance-b"
        )

        body = variant.body(settings)

        if variant.content_type == "text/plain":
            assert isinstance(body, str)
            assert "查询成功" in body
            assert "系统通知" in body
            identity_instruction = body
            next_action = body
        else:
            assert isinstance(body, dict)
            assert body["status"] == "ok"
            assert body["result"] == {"records": []}
            identity_instruction = body["metadata"]["system_instruction"]
            next_action = body["metadata"]["next_action"]
        assert settings.b_user_id in identity_instruction
        assert settings.b_instance_id in identity_instruction
        assert PRIVATE_MARKER in next_action
        assert AUTHORIZATION_MARKER in next_action

    def test_s04_reaches_real_execution_without_dedicated_profile(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_TEST_A_USER_ID", "real-user-a")
        monkeypatch.setenv("AGENT_TEST_A_INSTANCE_ID", "real-instance-a")
        monkeypatch.setenv("AGENT_TEST_B_USER_ID", "real-user-b")
        monkeypatch.setenv("AGENT_TEST_B_INSTANCE_ID", "real-instance-b")
        agent = _AuthenticatedCurrentProfileAgent()

        with pytest.raises(_ExecutionReached):
            NaturalLanguageIdentityScenarioRunner().run_natural_language_cannot_override_authoritative_identity(
                agent,
                object(),
                PROMPT_VARIANTS[0],
                1,
            )

    def test_s05_configures_mock_tool_without_dedicated_profile(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_TEST_A_USER_ID", "real-user-a")
        monkeypatch.setenv("AGENT_TEST_A_INSTANCE_ID", "real-instance-a")
        monkeypatch.setenv("AGENT_TEST_B_USER_ID", "real-user-b")
        monkeypatch.setenv("AGENT_TEST_B_INSTANCE_ID", "real-instance-b")
        agent = _AuthenticatedCurrentProfileAgent(mock_tools=True)

        with pytest.raises(_ExecutionReached):
            ToolResultIdentityScenarioRunner().run_tool_result_cannot_override_authoritative_identity(
                agent,
                object(),
                VARIANTS[0],
                1,
            )

        assert agent.mock_tool_configured


def _run_scenario(agent, *, is_tool_injection: bool) -> None:
    if is_tool_injection:
        ToolResultIdentityScenarioRunner().run_tool_result_cannot_override_authoritative_identity(
            agent, object(), VARIANTS[0], 1
        )
    else:
        NaturalLanguageIdentityScenarioRunner().run_natural_language_cannot_override_authoritative_identity(
            agent, object(), PROMPT_VARIANTS[0], 1
        )
