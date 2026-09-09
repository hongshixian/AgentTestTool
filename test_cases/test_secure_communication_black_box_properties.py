"""Verify secure-communication properties without source access."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.secure_communication_properties import SecureCommunicationPropertiesScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.3c-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS53CD101S0102SecureCommunicationBlackBoxProperties(SecureCommunicationPropertiesScenarioRunner):
    """测试用例 ID：ATS-5.3c-D1-01-S01-02

    测试用例名称：无源码时三属性替代检查

    测试目标：
        通过流量保密、报文篡改和重放验证通信三属性。

    前置条件：
        1. 测试订单查询正常对照可用。
        2. 原始流量和实际认证机制可操作。
        3. 可从新连接重放已消费请求。

    测试步骤：
        1. 查询订单并验证无密钥不能恢复业务内容。
        2. 移除认证信息或修改受保护订单号。
        3. 从新连接重放已消费请求。

    预期结果：
        1. 业务内容不明文且篡改被拒绝。
        2. 已消费报文重放被拒绝。
    """

    def test_black_box_three_communication_properties(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_secure_communication(agent_model, request, path="无源码三属性实测")
