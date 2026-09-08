"""Verify logs after a same-device account switch are attributed to the new user."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5d-D2-02-S03-01"
TEST_SAMPLE_ID = "ATS-5.5d-D2-02-S03"
TEST_PROMPT_ID = "01"


class TestATS55DD202S0301SwitchedUserLogAttributedToNewUser(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D2-02-S03-01

    测试用例名称：同一终端更换登录用户后日志归属新用户

    测试目标：
        验证同一终端从甲切换到乙后新任务日志归属乙。

    前置条件：
        1. 准备同终端账号切换、权威认证状态和用户归属日志。

    测试步骤：
        1. 甲执行任务并退出，乙登录后执行新任务并核对两次日志。

    预期结果：
        1. 两次任务分别归属甲乙且乙不会沿用甲身份。
    """

    def test_switched_user_log_attributed_to_new_user(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能自动退出和登录两个产品账号，也没有权威当前身份或用户归属日志 Provider，无法执行账号切换归属核查")
