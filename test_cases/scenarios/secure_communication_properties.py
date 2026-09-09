"""Model secure-communication property checks unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class SecureCommunicationPropertiesScenarioRunner(AgentTestCase):
    """Return not applicable without wire-level trust-boundary controls."""

    def run_unavailable_secure_communication(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求列出产品端到端每跳信任边界，并在真实通信层执行解密验证、认证篡改和已消费报文重放；当前CLI没有全链路流量、会话密钥或网络报文注入接口，无法执行核心核查"))
