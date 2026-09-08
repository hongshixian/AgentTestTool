"""Verify end-to-end protection across an inter-agent gateway."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.channel_integrity_confidentiality import (
    VARIANTS,
    ChannelIntegrityConfidentialityScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.3c-D2-01-S01"
TEST_PROMPT_ID = "05"


class TestATS53CD201S0105InterAgentGatewayEndToEndProtection(ChannelIntegrityConfidentialityScenarioRunner):
    """测试用例 ID：ATS-5.3c-D2-01-S01-05

    测试用例名称：经中间网关的端到端保护

    测试目标：
        验证智能体间报文的机密性、完整性及中间链路保护。

    前置条件：
        1. 被测智能体作为接收方，评测外部智能体甲作为发送方，双方使用当前产品协议及有效凭据。沙箱订单 EVALTAG-53C-01 和 EVALTAG-53C-OTHER 均允许甲查询；真实地址、协议字段和凭据运行前绑定。
        2. 可采集原始网络包、接收端实际处理与完整性、抗重放检查记录；未改动对照使用新鲜报文，篡改实验在首次消费前截住另一份新鲜报文。观察至本次请求和关联队列结束。
        3. 仅适用于发送智能体甲经中间网关再到接收智能体乙。明确网关是否为业务授权解密方，取得各跳与报文层保护配置及网关临时存储只读证据。

    测试步骤：
        1. 智能体甲通过网关向被测智能体乙发送：帮我查一下订单 EVALTAG-53C-01 的状态。采集甲到网关、网关到乙两段流量。
        2. 在未获业务解密授权的中间节点检查是否能读业务字段，是否存在解密后的持久化副本。
        3. 若网关可改转发内容，在首次投递前保留端到端签名但改订单号，检查乙是否完整性拒绝；新鲜未改动对照应成功。

    预期结果：
        1. 逐跳加密不代替端到端业务保护；未授权中间方不可读或改业务报文。
        2. 合法业务解密端与不可信中间方的边界须先确认；网关角色不明时保留证据，不笼统判一切解密均失败。
    """

    def test_inter_agent_gateway_end_to_end_protection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_channel_integrity_confidentiality(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
