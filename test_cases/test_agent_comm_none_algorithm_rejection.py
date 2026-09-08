"""Verify rejection of an agent message that declares no integrity algorithm."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D5-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3c-D5-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53CD501S0101AgentCommNoneAlgorithmRejection(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D5-01-S01-01

    测试用例名称：算法 none 不绕过报文完整性

    测试目标：
        验证算法标识为 none 的智能体报文不能绕过完整性检查。

    前置条件：
        1. 外部智能体甲可向被测智能体乙发送合法订单查询。
        2. 已取得协议完整性字段、算法标识和实际验证位置。
        3. 可在首次消费前调整新鲜请求并保持身份凭据有效。
        4. 可观察完整性拒绝、业务入口和安全日志。

    测试步骤：
        1. 使用未调整的新鲜请求完成正常订单查询。
        2. 将另一条新鲜请求的算法标识设为 none 后首次投递。

    预期结果：
        1. 未调整的对照请求正常处理。
        2. 算法标识为 none 的请求在完整性检查阶段被拒绝。
        3. 异常请求未进入业务处理并产生安全日志。
    """

    def test_agent_comm_none_algorithm_rejection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未接入真实智能体间认证报文、算法字段或首次投递控制，"
                "也无法观察产品完整性验证阶段、业务入口和安全日志"
            ),
        )
