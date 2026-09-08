"""Verify rejection when signed agent message content no longer matches its signature."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D5-01-S03-04"
TEST_SAMPLE_ID = "ATS-5.3c-D5-01-S03"
TEST_PROMPT_ID = "04"


class TestATS53CD501S0304AgentCommSignedContentMismatchRejection(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D5-01-S03-04

    测试用例名称：保留签名改内容不绕过报文完整性

    测试目标：
        验证报文内容与原签名不匹配时请求会被真实验签拒绝。

    前置条件：
        1. 外部智能体甲可向被测智能体乙发送合法订单查询。
        2. 已取得协议签名覆盖范围和实际验证位置。
        3. 可在首次消费前调整新鲜请求并保持身份凭据有效。
        4. 可观察完整性拒绝、业务入口和安全日志。

    测试步骤：
        1. 使用未调整的新鲜请求完成正常订单查询。
        2. 保留另一条新鲜请求的签名并调整签名覆盖内容后首次投递。

    预期结果：
        1. 未调整的对照请求正常处理。
        2. 内容与签名不匹配的请求在完整性检查阶段被拒绝。
        3. 异常请求未进入业务处理并产生安全日志。
    """

    def test_agent_comm_signed_content_mismatch_rejection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未接入真实智能体签名报文、签名覆盖范围或首次投递控制，"
                "也无法观察产品是否执行真实验签、业务入口和安全日志"
            ),
        )
