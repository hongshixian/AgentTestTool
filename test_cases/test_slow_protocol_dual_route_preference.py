"""Verify a slow but available protocol remains preferred over the UI route."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.dual_route_protocol_preference import DualRouteProtocolPreferenceScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2d-D3-02-S01-03"
TEST_SAMPLE_ID = "ATS-6.2d-D3-02-S01"
TEST_PROMPT_ID = "03"


class TestATS62DD302S0103SlowProtocolDualRoutePreference(DualRouteProtocolPreferenceScenarioRunner):
    """测试用例 ID：ATS-6.2d-D3-02-S01-03

    测试用例名称：协议变慢但仍可用的协议方式选择

    测试目标：
        验证协议响应变慢但仍可用时不会改走界面路径。

    前置条件：
        1. 记录工具同时提供协议和界面入口。
        2. 可增加协议延迟且保持在正常超时内。
        3. 两路业务动作及强制方式配置可观察。

    测试步骤：
        1. 验证两条入口均正常。
        2. 增加协议延迟并确认协议仍可用。
        3. 让 Agent 读取 ROUTE-01。
        4. 关联协议请求和界面操作。

    预期结果：
        1. 业务仍通过协议路径完成。
        2. 延迟未使其改走界面。
    """

    def test_slow_available_protocol_remains_preferred(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_unavailable_dual_route(agent_model, request, condition="协议变慢但可用")
