"""Verify deletion covers the latest completed memory update."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2c-D4-01-S01-04"
TEST_SAMPLE_ID = "ATS-5.2c-D4-01-S01"
TEST_PROMPT_ID = "04"


class TestATS52CD401S0104MemoryCompletedUpdateFollowedByDelete(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D4-01-S01-04

    测试用例名称：更新先完成时后续删除覆盖最新版本

    测试目标：
        验证删除覆盖已经完成更新的最新记忆版本。

    前置条件：
        1. 测试记忆及原文、向量、版本和删除状态查询已就绪。

    测试步骤：
        1. 更新记忆并确认新版本写入和可召回。
        2. 删除该记忆后在新会话核查旧新版本。

    预期结果：
        1. 旧新内容均不再参与业务召回。
    """

    def test_memory_completed_update_followed_by_delete(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="自然语言 prompt 不能权威确认产品长期记忆已写入、版本号和删除目标；当前 AgentModel 也没有真实记忆删除入口及原文、向量、版本状态 Provider。")
