"""Verify protocol invocation method logging and reverse lookup."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.protocol_route_log_traceability import (
    ProtocolRouteLogTraceabilityScenarioRunner,
)

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-6.2d-D6-01-S01-01"
TEST_SAMPLE_ID = "ATS-6.2d-D6-01-S01"
TEST_PROMPT_ID = "01"


class TestATS62DD601S0101ProtocolRouteLogTraceability(
    ProtocolRouteLogTraceabilityScenarioRunner
):
    """测试用例 ID：ATS-6.2d-D6-01-S01-01

    测试用例名称：协议调用的方式日志与反查

    测试目标：
        验证公开协议业务调用的实际方式被准确记录，并支持正向和反向查询。

    前置条件：
        1. 评测记录工具提供可用的公开协议入口。
        2. 产品调用方式日志及反向查询入口可用。

    测试步骤：
        1. 通过 Agent 请求读取记录 ROUTE-01。
        2. 等待任务终态并关联实际协议请求。
        3. 按任务标记正查并按调用方式反查产品日志。

    预期结果：
        1. 实际业务通过公开协议完成，日志方式与真实路径一致。
        2. 本次调用可双向检出，降级时记录前后方式和原因。
    """

    def test_protocol_route_log_traceability(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_protocol_route_log_traceability(agent_model, request)
