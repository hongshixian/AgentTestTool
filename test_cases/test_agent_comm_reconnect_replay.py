"""Verify that reconnecting does not permit an already processed agent request."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-08"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "08"


class TestATS53CD401S0108AgentCommReconnectReplay(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-08

    测试用例名称：断连重连后不再次执行已处理的旧请求

    测试目标：
        验证断连重连不会重置已处理请求的抗重放状态。

    前置条件：
        1. 订单智能体甲可向被测智能体发送经过认证的查询。
        2. 可保存并原样重交仍在其他有效期内的请求。
        3. 可中断和恢复智能体间连接且不重置业务数据。
        4. 可取得连接、抗重放和请求级业务执行记录。

    测试步骤：
        1. 发送并保存一条已成功处理的新请求。
        2. 中断并恢复连接后发送另一条新请求验证业务可用。
        3. 原样重交断连前已经处理的请求。

    预期结果：
        1. 重连前的原请求和重连后的新请求正常执行。
        2. 重交的旧请求被拒绝。
        3. 旧请求没有新增业务执行记录。
    """

    def test_agent_comm_reconnect_replay(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 不能截获并原样重放真实智能体认证报文，"
                "也没有智能体间连接中断恢复控制或请求级业务执行计数，无法验证重连抗重放"
            ),
        )
