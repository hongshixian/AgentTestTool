"""Model personal-information encryption inventory checks unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class PersonalInformationEncryptionInventoryScenarioRunner(AgentTestCase):
    """Return not applicable without product traffic and configuration access."""

    def run_unavailable_encryption_inventory(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求覆盖注册、资料、聊天、上传及后台链路的解密流量、TLS配置和证书校验；当前CodeBuddy CLI适配器不提供账号资料入口、全链路抓包解密或服务端配置，无法完成核心核查"))
