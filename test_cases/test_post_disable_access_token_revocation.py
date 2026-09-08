"""Verify an access token cannot access protected data after account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S02-03"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S02"
TEST_PROMPT_ID = "03"


class TestATS72BD201S0203PostDisableAccessTokenRevocation(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S02-03

    测试用例名称：账号停用后访问令牌不能取回访问

    测试目标：
        验证账号停用生效后原访问令牌不能继续访问受保护资料。

    前置条件：
        1. 甲有效访问令牌、乙对照账号及资料 API 基线已就绪。
        2. 管理员可停用甲并确认后端生效时间。

    测试步骤：
        1. 管理员停用甲并等待后端确认生效。
        2. 用甲原访问令牌重放资料请求。
        3. 由乙读取自身资料作为服务对照。

    预期结果：
        1. 后端在时限内拒绝甲原令牌且不执行资料读取。
        2. 拒绝不依赖自然过期，乙不受影响。
    """

    def test_post_disable_access_token_revocation(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能获取或重放产品访问令牌，也不能由管理员真实停用账号并确认生效，且没有令牌有效期和资料访问证据 Provider。")
