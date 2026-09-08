"""Verify a refresh token works before account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S01-04"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S01"
TEST_PROMPT_ID = "04"


class TestATS72BD201S0104PreDisableRefreshTokenBaseline(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S01-04

    测试用例名称：停用前刷新令牌真实可用基线

    测试目标：
        验证账号停用前刷新令牌可换取能访问受保护资料的新令牌。

    前置条件：
        1. 甲真实刷新令牌、刷新端点和个人资料 API 已就绪。
        2. 令牌轮换、归属及有效期可核对。

    测试步骤：
        1. 用甲刷新令牌调用真实刷新端点。
        2. 用新访问令牌读取甲的个人资料。
        3. 由乙读取自身资料作为服务对照。

    预期结果：
        1. 刷新成功且新令牌只能访问甲资料。
        2. 乙资料访问正常且与甲隔离。
    """

    def test_pre_disable_refresh_token_baseline(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不提供产品刷新令牌、刷新端点或个人资料 API 操作，也没有权威令牌轮换、归属和有效期 Provider。")
