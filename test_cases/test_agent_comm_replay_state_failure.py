"""Verify that an agent fails closed when replay-protection state is unavailable."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "05"


class TestATS53CD401S0105AgentCommReplayStateFailure(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-05

    测试用例名称：抗重放状态不可用时拒绝处理消息

    测试目标：
        验证可信抗重放状态不可用时被测智能体拒绝处理消息。

    前置条件：
        1. 订单智能体甲可向被测智能体发送经过认证的新鲜查询。
        2. 已确认实际协议使用的随机数缓存或序列号状态。
        3. 可在业务服务正常时使可信抗重放状态不可读写。
        4. 可取得状态故障、抗重放校验和业务接收记录。

    测试步骤：
        1. 状态正常时发送新鲜查询并保存成功记录。
        2. 使抗重放状态不可用后发送另一条新鲜查询。
        3. 恢复状态存储后发送新消息验证查询恢复。

    预期结果：
        1. 状态正常时的前后两条对照查询成功。
        2. 状态不可用期间的查询被拒绝处理。
        3. 被测智能体未以暂时免检方式放行业务请求。
    """

    def test_agent_comm_replay_state_failure(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未接入产品真实随机数缓存或序列号状态存储，"
                "不能在业务可用时注入其读写故障，也没有抗重放校验与业务处理证据"
            ),
        )
