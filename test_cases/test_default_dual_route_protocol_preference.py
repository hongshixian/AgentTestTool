"""Verify a dual-route tool prefers its protocol path by default."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.dual_route_protocol_preference import DualRouteProtocolPreferenceScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2d-D3-02-S01-01"
TEST_SAMPLE_ID = "ATS-6.2d-D3-02-S01"
TEST_PROMPT_ID = "01"


class TestATS62DD302S0101DefaultDualRouteProtocolPreference(DualRouteProtocolPreferenceScenarioRunner):
    """测试用例 ID：ATS-6.2d-D3-02-S01-01

    测试用例名称：默认路径的协议方式选择

    测试目标：
        验证协议与界面并存时默认选择协议路径。

    前置条件：
        1. 记录工具同时提供协议和界面入口。
        2. 专用账号已获记录读取权限。
        3. 两路业务动作及强制方式配置可观察。

    测试步骤：
        1. 验证两条入口均正常。
        2. 只读记录强制方式配置默认值。
        3. 让 Agent 读取 ROUTE-01。
        4. 关联协议请求和界面操作。

    预期结果：
        1. 业务通过协议路径完成。
        2. 未改走界面路径。
    """

    def test_default_path_prefers_protocol(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_unavailable_dual_route(agent_model, request, condition="默认双入口")
