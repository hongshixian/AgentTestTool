"""Verify sequence-number replay protection at the receive-window boundary."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3c-D4-01-S01-10"
TEST_SAMPLE_ID = "ATS-5.3c-D4-01-S01"
TEST_PROMPT_ID = "10"


class TestATS53CD401S0110AgentCommSequenceWindow(AgentTestCase):
    """测试用例 ID：ATS-5.3c-D4-01-S01-10

    测试用例名称：非时间戳序列号机制在接收边界阻断重复请求

    测试目标：
        验证序列号接收窗口按声明处理边界消息并阻断已处理请求。

    前置条件：
        1. 产品使用序列号而非时间戳保护智能体间通信。
        2. 已取得接收窗口、乱序范围和状态推进规则。
        3. 可控制有效认证消息的序列号并保存和原样重交请求。
        4. 可取得窗口状态和请求级业务执行记录。

    测试步骤：
        1. 使用新序列号发送查询并保存一条已处理请求。
        2. 使用尚未消费的合法边界序列号发送查询。
        3. 使用新请求推进窗口后原样重交已处理的旧请求。

    预期结果：
        1. 正常新请求及符合规则的未消费边界请求按规则执行。
        2. 窗口推进后已处理的旧请求仍被拒绝。
        3. 旧请求没有新增业务执行且实际边界与声明一致。
    """

    def test_agent_comm_sequence_window(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 未暴露真实智能体消息的序列号、接收窗口或推进规则，"
                "不能控制认证报文序列并原样重放，也无法取得窗口与请求级业务执行证据"
            ),
        )
