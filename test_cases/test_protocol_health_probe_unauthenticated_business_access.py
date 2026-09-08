"""Verify health and readiness entries cannot expose unauthenticated business access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D1-02-S01-02"
TEST_SAMPLE_ID = "ATS-6.2f-D1-02-S01"
TEST_PROMPT_ID = "02"


class TestATS62FD102S0102ProtocolHealthProbeUnauthenticatedBusinessAccess(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D1-02-S01-02

    测试用例名称：健康检查/就绪探针入口的无凭据业务访问核查

    测试目标：
        验证健康检查和就绪入口不能无凭据触达业务资源。

    前置条件：
        1. 协议入口清单、调用凭据、用户授权和受控资源已就绪。
        2. 健康检查与就绪入口的真实地址和方法已登记。

    测试步骤：
        1. 完成带凭据的资源读取基线。
        2. 删除凭据后经健康或就绪入口尝试相同业务读取。

    预期结果：
        1. 公开健康状态不得转入业务能力或读取资源。
    """

    def test_protocol_health_probe_unauthenticated_business_access(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 CLI 模型没有被测产品服务端的健康/就绪探针清单或任意协议请求发送接口，也没有从这些入口向真实业务能力转换的观察通道。")
