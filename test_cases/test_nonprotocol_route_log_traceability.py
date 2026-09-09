"""Verify non-protocol invocation method logging and reverse lookup."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-6.2d-D6-01-S01-02"
TEST_SAMPLE_ID = "ATS-6.2d-D6-01-S01"
TEST_PROMPT_ID = "02"


class TestATS62DD601S0102NonProtocolRouteLogTraceability(AgentTestCase):
    """测试用例 ID：ATS-6.2d-D6-01-S01-02

    测试用例名称：非协议调用的方式日志与反查

    测试目标：
        验证仅界面访问的真实业务方式被准确记录，并支持正向和反向查询。

    前置条件：
        1. 评测记录工具提供可用的真实业务界面入口。
        2. 产品界面驱动、调用方式日志及反向查询入口可用。

    测试步骤：
        1. 通过 Agent 请求读取记录 ROUTE-01。
        2. 等待任务终态并关联实际界面操作。
        3. 按任务标记正查并按调用方式反查产品日志。

    预期结果：
        1. 实际业务仅通过界面访问完成，日志方式与真实路径一致。
        2. 本次调用可双向检出，降级时记录前后方式和原因。
    """

    def test_nonprotocol_route_log_traceability(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有真实业务界面自动化或非协议操作证据通道，"
                "无法触发并区分界面访问与普通授权弹窗"
            ),
        )
