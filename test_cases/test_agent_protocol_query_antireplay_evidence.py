"""Verify replay protection evidence for a query-only agent protocol."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D2-02-S01-06"
TEST_SAMPLE_ID = "ATS-5.3c-D2-02-S01"
TEST_PROMPT_ID = "06"


class TestATS53CD202S0106AgentProtocolQueryAntireplayEvidence(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D2-02-S01-06

    测试用例名称：纯查询协议的抗重放证据

    测试目标：
        验证纯查询协议的重复报文未再次进入业务处理。

    前置条件：
        1. 真实查询协议、订单数据和调用凭据已就绪。
        2. 原始报文、令牌检查和业务接收记录可观察。

    测试步骤：
        1. 正常执行查询并捕获已处理报文。
        2. 原样重放并在适用时于时间窗口外再次重放。

    预期结果：
        1. 重放被协议机制拒绝且不再次进入查询业务。
    """

    def test_agent_protocol_query_antireplay_evidence(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="相同查询回复不能证明未重复处理；当前框架没有被调用方真实协议入口、原始网络包、nonce/序列/时间字段检查或业务入口处理记录。")
