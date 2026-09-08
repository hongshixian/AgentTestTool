"""Verify an access token works before account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S01-03"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S01"
TEST_PROMPT_ID = "03"


class TestATS72BD201S0103PreDisableAccessTokenBaseline(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S01-03

    测试用例名称：停用前访问令牌真实可用基线

    测试目标：
        验证账号停用前访问令牌可调用受保护资料 API。

    前置条件：
        1. 甲乙真实访问令牌及个人资料 API 已就绪。
        2. 令牌归属、有效期和资源归属可核对。

    测试步骤：
        1. 用甲乙令牌分别调用个人资料 API。
        2. 保存甲的令牌有效期和后端成功结果。

    预期结果：
        1. 甲乙令牌各自只能访问其所属资料。
        2. 甲访问令牌在停用前真实有效。
    """

    def test_pre_disable_access_token_baseline(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不提供产品访问令牌获取或个人资料 API 调用能力，也没有权威令牌归属、有效期和资源归属 Provider。")
