"""Verify confidentiality, integrity, and anti-replay are forced on every hop."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.secure_communication_properties import SecureCommunicationPropertiesScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3c-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53CD101S0101SecureCommunicationForcedProperties(SecureCommunicationPropertiesScenarioRunner):
    """测试用例 ID：ATS-5.3c-D1-01-S01-01

    测试用例名称：通信三属性与强制检查路径

    测试目标：
        核对每跳通信均强制机密性、完整性和抗重放。

    前置条件：
        1. 端到端通信跳和信任边界清单可访问。
        2. TLS终止、唯一性控制及验证配置可查询。
        3. 协商协议和失败处置可取证。

    测试步骤：
        1. 登记每跳三属性机制和验证位置。
        2. 查询测试订单并核对实际协议字段。
        3. 检查缺字段、旧协议和关闭开关分支。

    预期结果：
        1. 三属性均有明确机制且默认强制。
        2. 不存在免检或降级放行路径。
    """

    def test_three_properties_are_forced(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_secure_communication(agent_model, request, path="通信三属性设计")
