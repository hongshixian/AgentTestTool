"""Verify a refresh token cannot regain access after account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S02-04"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S02"
TEST_PROMPT_ID = "04"


class TestATS72BD201S0204PostDisableRefreshTokenRevocation(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S02-04

    测试用例名称：账号停用后刷新令牌不能取回访问

    测试目标：
        验证账号停用生效后原刷新令牌不能换取可用访问令牌。

    前置条件：
        1. 甲有效刷新令牌、乙对照账号及资料 API 基线已就绪。
        2. 管理员可停用甲并确认后端生效时间。

    测试步骤：
        1. 管理员停用甲并等待后端确认生效。
        2. 用甲原刷新令牌调用刷新端点。
        3. 若返回新令牌则用其请求甲资料，并由乙执行对照访问。

    预期结果：
        1. 刷新被拒且不能获得可访问甲资料的新令牌。
        2. 拒绝在时限内发生且乙不受影响。
    """

    def test_post_disable_refresh_token_revocation(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能操作产品刷新令牌或管理员真实停用账号并确认生效，也没有令牌签发、有效期和资料访问证据 Provider。")
