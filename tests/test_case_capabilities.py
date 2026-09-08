"""Verify that partial CLI observations cannot enable full security cases."""

from types import SimpleNamespace

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.model import CodeBuddyAgentModel
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.base import AgentTestCase


class _Ledger:
    def record(self, source: str, kind: str, data: object) -> None:
        pass


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


class TestSecurityCaseCapabilities:
    def test_codebuddy_helper_availability_does_not_upgrade_boundary_capability(
        self, tmp_path
    ) -> None:
        model = CodeBuddyAgentModel(
            workspace=tmp_path,
            driver=SimpleNamespace(),
            transport=SimpleNamespace(),
            credentials=SimpleNamespace(is_dedicated_test_account=True),
            evidence=SimpleNamespace(is_available=lambda: True),
            mock_tool=SimpleNamespace(),
            local_state=SimpleNamespace(is_available=lambda: True),
        )

        assert model.capabilities.external_observation
        assert model.capabilities.local_state_control
        assert model.capabilities.multiple_mock_tools
        assert model.capabilities.controlled_environment
        assert not model.capabilities.security_boundary_observation

    def test_external_helper_alone_does_not_enable_boundary_observation(self) -> None:
        agent = SimpleNamespace(
            capabilities=AgentCapabilities(external_observation=True),
            environment=SimpleNamespace(ledger=_Ledger()),
        )

        with pytest.raises(AssessmentOutcomeSignal, match="完整安全边界") as outcome:
            AgentTestCase().require_security_boundary_observation(agent, _request())

        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE

    def test_boundary_observation_requires_a_public_observation_provider(self) -> None:
        agent = SimpleNamespace(
            capabilities=AgentCapabilities(security_boundary_observation=True),
            environment=SimpleNamespace(ledger=_Ledger()),
        )

        with pytest.raises(AssessmentOutcomeSignal, match="公开") as outcome:
            AgentTestCase().require_security_boundary_observation(agent, _request())

        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
