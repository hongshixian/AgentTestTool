"""Model non-protocol route checks unavailable to the CLI adapter."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class NonProtocolRouteConsistencyScenarioRunner(AgentTestCase):
    """Return not applicable without observable product UI routing."""

    def run_unavailable_route_path(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        route: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{route}路径必须配置实际界面型工具或同时提供协议与界面入口，并观察屏幕读取、"
                "无障碍和模拟点击；当前 CodeBuddy CLI 适配器仅接入 STDIO MCP 工具，没有"
                "受控界面工具、界面自动化取证或业务协议端点阻断能力，无法完成核心操作"
            ),
        )
