"""Verify password login is rejected after account disablement."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-01-S02-05"
TEST_SAMPLE_ID = "ATS-7.2b-D2-01-S02"
TEST_PROMPT_ID = "05"


class TestATS72BD201S0205PostDisablePasswordLoginRejection(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-01-S02-05

    测试用例名称：账号停用后密码新登录被拒

    测试目标：
        验证账号停用生效后正确密码也不能建立可用新会话。

    前置条件：
        1. 甲乙密码登录与个人资料访问基线已就绪。
        2. 管理员可停用甲并确认后端生效时间。

    测试步骤：
        1. 管理员停用甲并等待后端确认生效。
        2. 在新会话用甲的正确账号和密码登录。
        3. 若签发凭证则请求甲资料，并由乙执行对照登录。

    预期结果：
        1. 甲新登录被拒且不能建立可用会话。
        2. 乙正常登录和资料访问不受影响。
    """

    def test_post_disable_password_login_rejection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不支持自动输入真实产品密码登录、切换专用账号或由管理员停用账号并确认生效，也没有新凭证签发和资料访问 Provider。")
