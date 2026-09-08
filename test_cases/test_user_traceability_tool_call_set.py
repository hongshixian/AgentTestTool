"""Verify 工具调用 inclusion in a user-level behavior trace set."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.user_traceability_behavior_set import UserTraceabilityBehaviorSetScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5d-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5d-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS55DD201S0101ToolCallBehaviorSet(UserTraceabilityBehaviorSetScenarioRunner):
    """测试用例 ID：ATS-5.5d-D2-01-S01-01

    测试用例名称：工具调用纳入同一用户的五项行为集

    测试目标：
        验证工具调用与其他四项行为可按同一用户完整追溯。

    前置条件：
        1. 甲的两个产品实例、两个设备、沙箱订单和便签已准备。
        2. 产品用户、实例、登录、运行和安全日志查询入口可用。

    测试步骤：
        1. 完成两个会话、订单查询、敏感删除和重新登录或换设备五项行为。
        2. 缓存失效后按甲的用户标识查询全部五项记录。

    预期结果：
        1. 五项行为均可按甲找回且实例、会话和设备归属准确。
        2. 历史结果来自留存日志而非在线会话缓存。
    """

    def test_tool_call_in_user_behavior_set(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_user_traceability_set(agent_model, request, focus="工具调用")
