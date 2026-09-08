"""Verify concurrent duplicate protocol tokens are accepted at most once."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-02-S01-03"
TEST_SAMPLE_ID = "ATS-5.3c-D2-02-S01"
TEST_PROMPT_ID = "03"


class TestATS53CD202S0103AgentProtocolConcurrentDuplicateToken(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D2-02-S01-03

    测试用例名称：并发重复令牌

    测试目标：
        验证字节相同的并发协议报文最多执行一次。

    前置条件：
        1. 真实协作协议、报文拦截和工单账本已就绪。
        2. 接收与提交时刻和抗重放记录可观察。

    测试步骤：
        1. 在首次投递前截住完整创建工单报文。
        2. 并发投递两份字节相同的副本。

    预期结果：
        1. 最多一份通过且工单只增加一条。
    """

    def test_agent_protocol_concurrent_duplicate_token(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前编排器可并发执行测试任务，但不能在被测产品智能体协议首次消费前截获并复制同一真实报文，也没有服务端接收提交时刻和抗重放证据。")
