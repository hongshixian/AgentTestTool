"""Model full encryption-channel coverage unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class EncryptionChannelCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without full product traffic observability."""

    def run_unavailable_channel_coverage(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, scope: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{scope}要求捕获客户端、服务端、模型、内部服务及第三方旁路的实际个人信息流量；当前第三方CLI只能观察自身STDIO和受控工具I/O，无法覆盖产品内部及SDK链路，核心操作不可执行"))
