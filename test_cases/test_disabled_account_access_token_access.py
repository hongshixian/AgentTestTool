"""Verify that a disabled account cannot regain access with an existing access token."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-02"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "02"


class TestATS72BD501S0102DisabledAccountAccessTokenAccess(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-02

    测试用例名称：账号停用后访问令牌不能取回访问

    测试目标：
        验证账号停用生效后，停用前有效的访问令牌不能继续访问受保护资源。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 已取得甲的有效访问令牌、资料 API 和令牌自然有效期。
        3. 已取得账号状态、请求和资料服务事件的公开观察能力。

    测试步骤：
        1. 使用甲访问令牌和乙凭据分别完成资料访问基线。
        2. 管理员停用账号甲并确认后端生效。
        3. 使用甲的同一访问令牌再次请求甲资料。
        4. 在生效窗口内复核甲令牌有效期和乙对照访问。

    预期结果：
        1. 后端拒绝甲的旧访问令牌请求。
        2. 资料服务不执行甲的新读取，且拒绝不依赖令牌自然过期。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_rejects_existing_access_token(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 不公开访问令牌或资料 API 认证字段，也没有管理员账号停用/恢复和真实甲乙"
            "资料资源接口，不能安全执行并权威观察本行状态转换"
        ))
