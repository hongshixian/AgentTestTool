"""Verify that partial CLI observations cannot enable full security cases."""

from types import SimpleNamespace

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.model import CodeBuddyAgentModel
from test_cases.base import AgentTestCase


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
            capabilities=AgentCapabilities(external_observation=True)
        )

        with pytest.raises(pytest.skip.Exception, match="完整安全边界"):
            AgentTestCase().require_security_boundary_observation(agent)

    def test_boundary_observation_requires_a_public_observation_provider(self) -> None:
        agent = SimpleNamespace(
            capabilities=AgentCapabilities(security_boundary_observation=True)
        )

        with pytest.raises(pytest.skip.Exception, match="公开"):
            AgentTestCase().require_security_boundary_observation(agent)
