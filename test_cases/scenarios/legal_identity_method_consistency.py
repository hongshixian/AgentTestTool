"""Model unsupported legal identity method consistency paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class LegalIdentityMethodConsistencyScenarioRunner(AgentTestCase):
    """Return not applicable without public identity-context control."""

    def run_legal_identity_method_consistency(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, scope: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须枚举{scope}实际共同支持的认证方式，逐种绑定合法凭据并观察系统身份向下游贯通。当前 AgentModel 无多认证方式配置、权威用户上下文、工具端真实身份或端云映射接口，无法执行本行"))
