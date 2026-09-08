"""Model third-party consent decisions unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ThirdPartyConsentPrecedenceScenarioRunner(AgentTestCase):
    """Return not applicable without product-native consent control."""

    def run_unavailable_consent_choice(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, choice: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(f"向第三方提交前选择{choice}必须从干净未同意状态触发产品真实同意界面并记录选择时刻；当前CodeBuddy print模式没有第三方同意状态、界面选择或同意事件接口，配置Mock Tool不能代表产品已取得同意"),
        )
