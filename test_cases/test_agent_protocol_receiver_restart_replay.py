"""Verify replay protection survives an agent-protocol receiver restart."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-02-S01-05"
TEST_SAMPLE_ID = "ATS-5.3c-D2-02-S01"
TEST_PROMPT_ID = "05"


class TestATS53CD202S0105AgentProtocolReceiverRestartReplay(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D2-02-S01-05

    测试用例名称：接收进程重启后重放

    测试目标：
        验证接收进程重启后仍拒绝重启前的已消费报文。

    前置条件：
        1. 真实接收服务、批准的重启入口和工单账本已就绪。
        2. 完整报文和抗重放状态可观察。

    测试步骤：
        1. 正常消费创建工单报文并保存副本。
        2. 重启接收进程后原样重发旧报文。

    预期结果：
        1. 重启恢复后旧报文仍被拒绝且工单不增加。
    """

    def test_agent_protocol_receiver_restart_replay(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架只能管理自身 Mock 接收端和 CLI 子进程，不能重启产品真实智能体协议接收服务、保存其抗重放状态或投递重启前的原始报文。")
