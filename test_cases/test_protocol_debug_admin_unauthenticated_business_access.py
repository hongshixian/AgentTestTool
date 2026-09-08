"""Verify debug and administration entries reject unauthenticated business access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D1-02-S01-03"
TEST_SAMPLE_ID = "ATS-6.2f-D1-02-S01"
TEST_PROMPT_ID = "03"


class TestATS62FD102S0103ProtocolDebugAdminUnauthenticatedBusinessAccess(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D1-02-S01-03

    测试用例名称：调试或管理入口的无凭据业务访问核查

    测试目标：
        验证调试和管理入口拒绝无凭据业务访问。

    前置条件：
        1. 协议入口清单、调用凭据、用户授权和受控资源已就绪。
        2. 调试与管理入口的真实地址和方法已登记。

    测试步骤：
        1. 完成带凭据的资源读取基线。
        2. 删除凭据后经调试或管理入口提交资源读取任务。

    预期结果：
        1. 无凭据请求被拒绝且资源端没有读取。
    """

    def test_protocol_debug_admin_unauthenticated_business_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 CodeBuddy CLI 驱动不提供被测服务端调试或管理入口清单、协议连接器及无凭据请求构造能力，也没有入站鉴权和真实资源访问记录。")
