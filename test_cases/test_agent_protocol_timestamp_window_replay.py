"""Verify consumed agent messages are rejected inside and outside the timestamp window."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.3c-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS53CD202S0102AgentProtocolTimestampWindowReplay(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D2-02-S01-02

    测试用例名称：时间窗口内外重放

    测试目标：
        验证已消费报文在时间窗口内外重放均被拒绝。

    前置条件：
        1. 真实时间戳机制、接受窗口和工单账本已就绪。
        2. 完整报文可捕获并按指定时刻原样投递。

    测试步骤：
        1. 正常消费报文并保存时间戳令牌。
        2. 在声明窗口内外分别原样重放并发送新鲜对照。

    预期结果：
        1. 两次重放均被拒绝且新鲜请求正常。
    """

    def test_agent_protocol_timestamp_window_replay(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能取得被测 Agent 协作协议的真实时间戳机制、接受窗口或原始报文，也没有协议级重放连接器、抗重放记录和工单账本。")
