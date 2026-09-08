"""Model voluntary third-party consent paths unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class VoluntaryThirdPartyConsentScenarioRunner(AgentTestCase):
    """Return not applicable without consent UI and account-group controls."""

    def run_unavailable_voluntary_consent(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求产品同意界面、第三方独立选择/撤回状态及相关账号属性；当前CodeBuddy CLI没有同意界面自动化、产品同意状态或特殊群体账号配置接口，无法完成核心操作"))
