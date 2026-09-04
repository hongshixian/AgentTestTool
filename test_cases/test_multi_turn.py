"""Verify that the Agent retains context across multiple turns."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase


pytestmark = pytest.mark.e2e


class TestATS00XD200S01MultiTurn(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D2-00-S01（本条用例是示例用例）

    测试用例名称：Agent 多轮会话上下文保持

    测试目标：
        验证 Agent 能够在同一会话的后续轮次中正确使用前文信息。

    前置条件：
        1. 被测 Agent CLI 已安装。
        2. 被测 Agent 已完成登录认证。
        3. 被测 Agent 支持多轮会话。
        4. Judge 模型 API 配置可用。

    测试步骤：
        1. 初始化被测 Agent Model。
        2. 检查 Agent 登录状态和多轮会话能力。
        3. 在第一轮要求 Agent 记住指定验证码。
        4. 在第二轮询问第一轮提供的验证码。
        5. 使用 Judge 模型评价第二轮返回。

    预期结果：
        1. 两轮交互均正常完成。
        2. Agent 在第二轮准确返回第一轮提供的验证码。
        3. Judge 模型判定多轮上下文保持能力通过。
    """

    def test_agent_retains_context_across_turns(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge,
    ) -> None:
        self.assert_agent_authenticated(agent_model)
        if not agent_model.capabilities.multi_turn:
            pytest.skip("当前 Agent 不支持多轮会话")

        verification_code = "K7M4-Q2P9"
        first_prompt = f"请记住验证码 {verification_code}，只回复“已记住”。"
        first_turn = agent_model.send_prompt(first_prompt)
        self.assert_turn_completed(first_turn)

        second_prompt = "我刚才让你记住的验证码是什么？只回复验证码。"
        second_turn = agent_model.send_prompt(second_prompt)
        self.assert_turn_completed(second_turn)

        verdict = judge_model.evaluate(
            prompt=second_prompt,
            turn=second_turn,
            criterion=(
                f"Agent 应准确返回验证码 {verification_code}。"
                "允许 Markdown 或少量解释，但不得返回其他验证码或表示不知道前文。"
            ),
        )
        assert verdict.passed, verdict.reason
