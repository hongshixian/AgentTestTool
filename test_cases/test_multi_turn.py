"""Verify that the Agent retains context across multiple turns."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D2-00-S01"
TURN_TIMEOUT_SECONDS = 180.0


class TestATS00XD200S01MultiTurn(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D2-00-S01（本条用例是示例用例）

    测试用例名称：同一会话跨轮回忆验证码（冒烟示例）

    测试目标：
        验证 Agent 能够在同一会话的后续轮次中正确使用前文信息。

    前置条件：
        1. Agent CLI 已安装并完成登录。
        2. Agent 支持连续多轮交互。

    测试步骤：
        1. 启动 Agent 交互会话。
        2. 第一轮要求记住 K7M4-Q2P9，并仅回复“已记住”。
        3. 同一会话第二轮询问刚才的验证码，要求仅回复验证码。

    预期结果：
        1. 两轮交互均正常完成。
        2. 第二轮准确返回 K7M4-Q2P9。
    """

    def test_agent_retains_context_across_turns(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.assert_agent_authenticated(agent_model, request)
        if not agent_model.capabilities.multi_turn:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason="被测 Agent 不具备多轮会话能力",
            )
        verification_code = "K7M4-Q2P9"
        first_prompt = f"请记住验证码 {verification_code}，只回复“已记住”。"
        first_turn = agent_model.send_prompt(first_prompt, timeout=TURN_TIMEOUT_SECONDS)
        self.assert_turn_completed(first_turn, request, agent_model)

        second_prompt = "我刚才让你记住的验证码是什么？只回复验证码。"
        second_turn = agent_model.send_prompt(second_prompt, timeout=TURN_TIMEOUT_SECONDS)
        self.assert_turn_completed(second_turn, request, agent_model)
        if second_turn.response.strip() != verification_code:
            self.conclude_failed(
                request,
                agent_model,
                reason="第二轮未准确返回第一轮提供的验证码",
            )

        self.conclude_passed(
            request,
            agent_model,
            reason="Agent 在同一会话第二轮准确返回了第一轮验证码",
        )
