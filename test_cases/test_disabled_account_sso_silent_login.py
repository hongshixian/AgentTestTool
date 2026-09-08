"""Verify that SSO silent login cannot reactivate access to a disabled account."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-07"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "07"


class TestATS72BD501S0107DisabledAccountSSOSilentLogin(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-07

    测试用例名称：账号停用后 SSO 静默登录不能取回访问

    测试目标：
        验证企业 SSO 会话仍有效时，静默登录不能恢复被停账号的服务访问。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 账号甲绑定当前有效的测试企业 SSO 身份和可核验本地映射。
        3. 已取得管理员、SSO 登录、本服务会话和资料事件的公开观察能力。

    测试步骤：
        1. 经 SSO 正常登录并完成甲资料访问基线，同时确认乙对照。
        2. 管理员停用账号甲并确认后端生效。
        3. 保持身份提供商会话有效并尝试本服务 SSO 静默登录。
        4. 在获得本服务会话时请求甲资料并复核乙对照。

    预期结果：
        1. 本服务不会恢复被停账号甲的会话或资源访问。
        2. 身份提供商会话仍在线不会改变甲的停用状态。
        3. 对照账号乙不受影响。
    """

    def test_sso_silent_login_does_not_restore_disabled_account(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 没有企业 SSO 身份绑定、浏览器静默登录、管理员账号停用或本地账号"
            "映射接口，也不能观察本服务会话与真实资料访问，无法执行本行测试"
        ))
