"""Model product-native authorization denial actions unavailable to CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class AuthorizationDenialActionScenarioRunner(AgentTestCase):
    """Return not applicable when an authorization decision cannot be controlled."""

    def run_unavailable_denial_action(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        action: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须在产品原生消息发送授权界面执行“{action}”，并读取账号授权清单和"
                "授权事件；当前 CodeBuddy print 模式固定跳过工具权限确认，不提供该界面、"
                "决策操作或权威授权状态接口，无法完成核心步骤"
            ),
        )
