"""Verify that another browser session loses access when its account is disabled."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-09"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "09"


class TestATS72BD501S0109DisabledAccountOtherBrowserSession(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-09

    测试用例名称：账号停用后另一浏览器旧会话不能取回访问

    测试目标：
        验证账号停用生效后，停用前已在线的另一浏览器会话同步失效。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 账号甲在两个独立浏览器中同时保持有效会话。
        3. 已取得管理员、浏览器请求和资料服务事件的公开观察能力。

    测试步骤：
        1. 从浏览器乙完成甲资料访问基线，并确认账号乙对照正常。
        2. 管理员从独立入口停用账号甲并确认后端生效。
        3. 从浏览器乙原会话再次请求甲资料。
        4. 在生效窗口内复核会话有效期和乙对照访问。

    预期结果：
        1. 后端拒绝另一浏览器中的甲旧会话。
        2. 资料服务不执行甲的新读取。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_invalidates_other_browser_session(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前框架没有多浏览器会话、Cookie、管理员停用和真实资料资源控制，也不能观察权威"
            "后端账号状态与资料事件，无法执行本行测试"
        ))
