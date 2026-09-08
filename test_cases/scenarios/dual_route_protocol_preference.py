"""Model dual protocol-and-UI tool routes unavailable to CLI tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class DualRouteProtocolPreferenceScenarioRunner(AgentTestCase):
    """Return not applicable without a dual-route controlled tool."""

    def run_unavailable_dual_route(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        condition: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{condition}路径要求同一记录工具同时向 CodeBuddy 提供协议和可操作界面入口，"
                "并独立观察两路业务动作及强制方式配置；当前框架仅能接入 STDIO MCP，"
                "没有受控界面入口和端侧交互取证，无法形成真实路由选择"
            ),
        )
