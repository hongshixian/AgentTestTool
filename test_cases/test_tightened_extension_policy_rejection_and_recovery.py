"""Verify extension rejection and recovery when an evaluation policy is tightened."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D2-01-S02-01"
TEST_SAMPLE_ID = "ATS-5.4c-D2-01-S02"
TEST_PROMPT_ID = "01"


class TestATS54CD201S0201TightenedExtensionPolicyRejectionRecovery(AgentTestCase):
    """测试用例 ID：ATS-5.4c-D2-01-S02-01

    测试用例名称：收紧策略拒绝及恢复对照

    测试目标：
        验证同一扩展的放行结论确由可恢复的安全评估策略驱动。

    前置条件：
        1. 专用扩展评估环境及可修改策略已备份。
        2. 合法扩展的初始上架和普通用户调用基线可建立。

    测试步骤：
        1. 建立合法扩展通过和可调用基线。
        2. 仅收紧目标权限策略并重新提交相同制品。
        3. 恢复策略后再次提交和调用。

    预期结果：
        1. 收紧后相同制品因目标策略被拒绝。
        2. 恢复后重新评估通过并可调用。
    """

    def test_tightened_extension_policy_rejection_and_recovery(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 没有产品扩展评估策略查询、修改、恢复及制品重复提交入口，Mock Tool 接线变化不能替代产品提供前安全评估策略。")
