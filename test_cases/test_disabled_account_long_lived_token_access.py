"""Verify that a disabled account cannot regain access with an existing long-lived token."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-05"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "05"


class TestATS72BD501S0105DisabledAccountLongLivedTokenAccess(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-05

    测试用例名称：账号停用后长期访问令牌不能取回访问

    测试目标：
        验证账号停用生效后，停用前的长期访问令牌不能继续访问受保护资源。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 账号甲持有有效的独立长期令牌和真实受保护接口。
        3. 已取得账号状态、请求和资料服务事件的公开观察能力。

    测试步骤：
        1. 使用甲长期令牌和乙凭据分别完成资料访问基线。
        2. 管理员停用账号甲并确认后端生效。
        3. 使用甲的同一长期令牌再次调用受保护接口。
        4. 在生效窗口内复核甲令牌有效期和乙对照访问。

    预期结果：
        1. 后端拒绝甲的旧长期令牌请求。
        2. 资料服务不执行甲的新读取。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_rejects_existing_long_lived_token(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 不公开长期访问令牌或用户级受保护接口，也没有管理员账号停用能力和"
            "权威资料服务事件观察，无法执行本行测试"
        ))
