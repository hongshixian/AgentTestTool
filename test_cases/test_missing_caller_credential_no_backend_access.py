"""Verify a request without caller credentials causes no backend access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.2f-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS62FD201S0101MissingCallerCredentialNoBackendAccess(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-01-S01-01

    测试用例名称：无调用方凭据不产生后端越权

    测试目标：
        验证缺少调用方凭据的协议请求被拒且不访问资源。

    前置条件：
        1. 真实调用方凭据、用户授权和资源读取基线已就绪。
        2. 入站报文、鉴别记录和资源访问可关联。

    测试步骤：
        1. 用合法调用方凭据和用户授权建立成功基线。
        2. 删除调用方凭据后通过同一协议路径提交读取任务。

    预期结果：
        1. 调用方鉴别拒绝且不产生资源操作。
        2. 拒绝响应不泄露秘密、配置或无权内容。
    """

    def test_missing_caller_credential_no_backend_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 将 CLI 作为被测客户端，不能把 Agent 作为协议接收方注入或删除调用方凭据，也没有入站鉴别记录和产品后端资源访问 Provider。")
