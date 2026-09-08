"""Verify sequence-based agent messages handle out-of-order delivery without replay."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.3c-D2-02-S01"
TEST_PROMPT_ID = "04"


class TestATS53CD202S0104AgentProtocolOutOfOrderSequence(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D2-02-S01-04

    测试用例名称：序列号乱序

    测试目标：
        验证乱序新鲜报文遵循声明策略且已消费序列不能重放。

    前置条件：
        1. 真实序列号机制、协议拦截和工单账本已就绪。
        2. 相邻序列号及抗重放记录可观察。

    测试步骤：
        1. 截住两个相邻序列号的新鲜报文并倒序投递。
        2. 原样重发已消费的较大序列号报文。

    预期结果：
        1. 乱序行为符合策略且已消费序列重放被拒绝。
    """

    def test_agent_protocol_out_of_order_sequence(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 CLI 适配不暴露真实智能体协议序列号、声明策略或报文投递控制，无法截获相邻新鲜报文并倒序发送或观察协议抗重放检查。")
