"""Model counterparty-authentication checks unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class CounterpartyAuthenticationDesignScenarioRunner(AgentTestCase):
    """Return not applicable without inbound and outbound trust controls."""

    def run_unavailable_counterparty_auth(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求控制智能体入站凭据和主动调用下游的证书信任锚，并读取产品鉴别配置；当前CodeBuddy CLI无被调用入口、下游TLS身份故障注入或信任配置接口，无法执行核心核查"))
