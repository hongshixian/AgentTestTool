"""Verify the backend effect of account disablement without source access."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2b-D1-01-S01-06"
TEST_SAMPLE_ID = "ATS-7.2b-D1-01-S01"
TEST_PROMPT_ID = "06"


class TestATS72BD101S0106AccountDisablementBackendEffectWithoutSource(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D1-01-S01-06

    测试用例名称：未开放源码时验证账号停用的实际后端效果

    测试目标：
        验证账号停用后旧有效凭证被后端拒绝且对照账号正常。

    前置条件：
        1. 服务商管理员可停用账号甲，并准备甲乙账号、个人资料和旧有效令牌。

    测试步骤：
        1. 停用账号甲后重放旧资料请求，并用账号乙执行对照请求。

    预期结果：
        1. 甲的旧有效令牌在时限内被拒绝，账号乙仍可正常访问。
    """

    def test_account_disablement_backend_effect_without_source(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架不能操作服务商账号停用、提取重放旧服务令牌或查询权威账号状态，无法触发此后端效果路径",
        )
