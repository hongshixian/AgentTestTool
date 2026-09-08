"""Verify account disablement enforcement in backend authentication paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2b-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-7.2b-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS72BD101S0102AccountDisablementBackendEnforcement(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D1-01-S01-02

    测试用例名称：后端鉴权强制点

    测试目标：
        验证登录、资料、任务和开放 API 都执行账号停用检查。

    前置条件：
        1. 取得当前鉴权实现、部署配置和真实请求样本的只读权限。

    测试步骤：
        1. 从真实请求链路核对停用态、会话和令牌状态检查点。

    预期结果：
        1. 各凭证路径均执行后端停用检查。
    """

    def test_account_disablement_backend_enforcement(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架不能读取产品鉴权实现、部署配置或服务端请求链路，无法核查后端停用强制点",
        )
