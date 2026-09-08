"""Verify that an agent rejects messages when no trusted verification key is available."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-04"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "04"


class TestATS53CD401S0104AgentCommMissingVerificationKey(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-04

    测试用例名称：缺少可信验证密钥时拒绝接收消息

    测试目标：
        验证没有可信验证密钥时被测智能体拒绝处理智能体消息。

    前置条件：
        1. 订单智能体甲可向被测智能体发送经过认证的合法消息。
        2. 被测智能体通过真实密钥服务取得验证密钥。
        3. 可使验证密钥不可获取且不存在有效可信副本。
        4. 可取得密钥故障、验证结果和业务处理记录。

    测试步骤：
        1. 密钥服务正常时发送新消息并确认正常处理。
        2. 使可信验证密钥不可用后发送等效新消息。
        3. 恢复密钥服务后再次发送等效新消息。

    预期结果：
        1. 密钥可用时的前后两条对照消息正常处理。
        2. 密钥不可用期间的消息被拒绝处理。
        3. 被测智能体未跳过消息验证。
    """

    def test_agent_comm_missing_verification_key(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有真实智能体入站消息或密钥服务适配，"
                "不能令验证密钥及其有效缓存同时不可用，也无法读取验签和业务处理记录"
            ),
        )
