"""Verify a web session cookie works before account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS72BD201S0101PreDisableWebCookieAccessBaseline(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S01-01

    测试用例名称：停用前Web 会话 Cookie真实可用基线

    测试目标：
        验证账号停用前 Web 会话 Cookie 可访问其受保护资料。

    前置条件：
        1. 甲乙真实 Web 账号、独立浏览器会话和个人资料已就绪。
        2. Cookie 归属、有效期及资料服务记录可核对。

    测试步骤：
        1. 甲乙分别通过 Web 登录并读取各自资料。
        2. 保存甲的有效 Cookie 和后端成功结果。

    预期结果：
        1. 甲乙凭证各自只能访问其所属资料。
        2. 甲 Cookie 在停用前真实有效。
    """

    def test_pre_disable_web_cookie_access_baseline(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 仅支持 CLI 会话，不能操作真实 Web 登录、浏览器 Cookie 或产品个人资料服务，也没有权威凭证归属和数据访问 Provider。")
