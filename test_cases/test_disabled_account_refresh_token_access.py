"""Verify that a disabled account cannot regain access by refreshing an existing token."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-03"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "03"


class TestATS72BD501S0103DisabledAccountRefreshTokenAccess(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-03

    测试用例名称：账号停用后刷新令牌不能取回访问

    测试目标：
        验证账号停用生效后，停用前的刷新令牌不能换取可访问资源的新令牌。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 已取得真实刷新端点、当前有效刷新令牌和令牌轮换规则。
        3. 已取得账号状态、令牌签发和资料服务事件的公开观察能力。

    测试步骤：
        1. 正常刷新一次并保存最新有效令牌，同时确认乙资料可访问。
        2. 管理员停用账号甲并确认后端生效。
        3. 使用甲的最新刷新令牌请求新令牌，并在返回时请求甲资料。
        4. 在生效窗口内复核令牌有效期和乙对照访问。

    预期结果：
        1. 刷新请求被拒绝且不签发可用的新访问令牌。
        2. 任何已返回令牌均不能访问甲资料。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_rejects_existing_refresh_token(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 不公开刷新令牌、刷新端点或令牌轮换流程，也没有管理员停用接口和真实"
            "资料服务事件观察，无法执行本行验证"
        ))
