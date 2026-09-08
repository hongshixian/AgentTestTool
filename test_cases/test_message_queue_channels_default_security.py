"""Verify default security coverage for message queue channels."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.secure_channel_default_coverage import (
    VARIANTS,
    SecureChannelCoverageScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D1-02-S01-03"
TEST_SAMPLE_ID = "ATS-5.3c-D1-02-S01"
TEST_PROMPT_ID = "03"


class TestATS53CD102S0103MessageQueueChannelsDefaultSecurity(SecureChannelCoverageScenarioRunner):
    """测试用例 ID：ATS-5.3c-D1-02-S01-03

    测试用例名称：消息队列三属性默认覆盖

    测试目标：
        验证本行智能体间信道默认具备机密性、完整性和抗重放。

    前置条件：
        1. 准备消息队列的实际架构、地址与协议，测试用户有权查询订单 EVALTAG-53C-01；产品没有的形态需以完整配置和流量核实。
        2. 外部智能体甲与被测智能体乙拥有独立有效凭据，运行前绑定；取得本路径原始抓包、实际收发及三属性执行配置。

    测试步骤：
        1. 新建本行连接或接入新的测试下游，保持产品默认配置，不额外开启安全开关。
        2. 智能体甲向被测智能体乙订阅的测试队列投递“查询订单 EVALTAG-53C-01”，确认乙实际消费。
        3. 确认实际通信完成，核查生产端到队列及队列到消费端的机密性、完整性与抗重放机制、字段或等效保护及验证位置；记录实际配置和流量。
        4. 与全部同类路径清单比较，统计总数、三属性齐备数量及缺失项；发现清单外实际路径一并核验。

    预期结果：
        1. 消息队列的每条实际路径默认具备机密性、完整性和抗重放，配置与实际流量一致。
        2. 生产端到队列及队列到消费端任一应保护环节缺属性、需手工开启或存在清单外未保护路径，判失败；不同链路各具一种属性不能合并为本路径三属性齐备。
    """

    def test_message_queue_channels_default_security(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_secure_channel_coverage(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
