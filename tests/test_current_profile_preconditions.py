"""Verify prompt-injection scenarios accept the currently authenticated profile."""

from __future__ import annotations

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.result import AuthResult, AuthStatus
from test_cases.scenarios.natural_language_identity_override import (
    PROMPT_VARIANTS,
    NaturalLanguageIdentityScenarioRunner,
)
from test_cases.scenarios.tool_result_identity_injection import (
    VARIANTS,
    ToolResultIdentityScenarioRunner,
)


class _ExecutionReached(RuntimeError):
    pass


class _AuthenticatedCurrentProfileAgent:
    def __init__(self, *, mock_tools: bool = False) -> None:
        self.capabilities = AgentCapabilities(
            multi_turn=True,
            mock_tools=mock_tools,
            dedicated_test_account=False,
        )
        self.mock_tool_configured = False

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED, "current profile is authenticated")

    def configure_mock_tool(self, profile, *, run_id: str) -> None:
        self.mock_tool_configured = True

    def send_prompt(self, prompt: str, **kwargs):
        raise _ExecutionReached


class TestCurrentProfilePreconditions:
    def test_s04_reaches_real_execution_without_dedicated_profile(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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
