"""Verify a web session cookie cannot access protected data after account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S02-01"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S02"
TEST_PROMPT_ID = "01"


class TestATS72BD201S0201PostDisableWebCookieAccessRevocation(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S02-01

    测试用例名称：账号停用后Web 会话 Cookie不能取回访问

    测试目标：
        验证账号停用生效后原 Web Cookie 不能继续访问受保护资料。

    前置条件：
        1. 甲有效 Web Cookie、乙对照账号及个人资料基线已就绪。
        2. 管理员可停用甲并确认后端生效时间。

    测试步骤：
        1. 管理员停用甲并等待后端确认生效。
        2. 沿用甲原 Cookie 重放资料请求。
        3. 由乙读取自身资料作为服务对照。

    预期结果：
        1. 后端在时限内拒绝甲原 Cookie 且不执行资料读取。
        2. 拒绝不依赖自然过期，乙不受影响。
    """

    def test_post_disable_web_cookie_access_revocation(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能操作 Web Cookie 或管理员真实停用账号并确认后端生效，也没有产品资料访问及凭证有效期证据 Provider。")
