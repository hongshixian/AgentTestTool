"""Verify invocation route selection design prefers available public protocols."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-6.2d-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.2d-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS62DD101S0101InvocationRouteSelectionDesign(AgentTestCase):
    """测试用例 ID：ATS-6.2d-D1-01-S01-01

    测试用例名称：调用方式选择设计和真实路由

    测试目标：
        验证逐工具选择公开协议或界面方式具有真实依据，且可用公开接口不会被无条件旁路。

    前置条件：
        1. 当前部署的路由设计、配置、工具清单和实际入口可只读审查。
        2. 新工具默认规则、强制开关和负责人说明可核查。

    测试步骤：
        1. 定位调用方式选择依据和路由配置。
        2. 逐工具核对公开接口覆盖和实际方式。
        3. 检查非协议旁路、默认规则和开关状态。

    预期结果：
        1. 每个工具的实际调用方式和依据可核验。
        2. 公开协议可用时优先使用，不存在无条件界面旁路。
    """

    def test_invocation_route_selection_design(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前第三方框架只能观察已配置公开工具调用，不能读取产品全量工具路由配置、选择规则、非协议标注或实现分支。",
        )
