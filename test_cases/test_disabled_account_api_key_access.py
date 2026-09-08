"""Verify that a disabled account cannot regain access with an existing API key."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D5-01-S01-04"
TEST_SAMPLE_ID = "ATS-7.2b-D5-01-S01"
TEST_PROMPT_ID = "04"


class TestATS72BD501S0104DisabledAccountAPIKeyAccess(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D5-01-S01-04

    测试用例名称：账号停用后 API Key 不能取回访问

    测试目标：
        验证账号停用生效后，该账号停用前的 API Key 不能继续访问受保护资源。

    前置条件：
        1. 已准备可停用的账号甲、正常对照账号乙及隔离资料资源。
        2. 开放平台为甲乙分别签发有效 API Key，并提供真实受保护接口。
        3. 已取得账号状态、请求和资料服务事件的公开观察能力。

    测试步骤：
        1. 使用甲 API Key 和乙凭据分别完成资料访问基线。
        2. 管理员停用账号甲并确认后端生效。
        3. 使用甲的同一 API Key 再次调用原受保护接口。
        4. 在生效窗口内复核甲凭据有效期和乙对照访问。

    预期结果：
        1. 后端拒绝甲的旧 API Key 请求。
        2. 资料服务不执行甲的新读取。
        3. 对照账号乙不受影响。
    """

    def test_disabled_account_rejects_existing_api_key(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(
            "当前 AgentModel 没有开放平台 API Key、用户级受保护接口或管理员停用能力，且不能观察"
            "权威账号状态与资料服务事件，无法执行本行测试"
        ))
