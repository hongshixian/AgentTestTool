"""Verify regional routing evidence under simulated overseas access."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2f-D3-03-S01-03"
TEST_SAMPLE_ID = "ATS-5.2f-D3-03-S01"
TEST_PROMPT_ID = "03"


class TestATS52FD303S0103SimulatedOverseasAccessRegionRoutingEvidence(AgentTestCase):
    """测试用例 ID：ATS-5.2f-D3-03-S01-03

    测试用例名称：境外出口受限时的区域路由替代取证

    测试目标：
        验证模拟境外接入时境内账号仍按属地路由到境内存储。

    前置条件：
        1. 产品测试环境可模拟境内和境外接入区域。
        2. 模拟设置、强制路由和实际存储区域可查询。

    测试步骤：
        1. 在模拟境内和境外接入状态分别写入测试记忆。
        2. 对比模拟设置、实际存储区域和副本位置。

    预期结果：
        1. 两次写入及副本均保持境内存储。
        2. 路由配置和模拟行为一致。
    """

    def test_simulated_overseas_access_region_routing_evidence(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 没有产品接入区域模拟入口，也不能查询产品属地路由、实际存储 region 或全部副本位置；本地工作目录不代表产品服务端存储区域。")
