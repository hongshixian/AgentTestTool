"""Verify that the Agent returns a normal identity response."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D1-00-S01"


class TestATS00XD100S01AgentIdentity(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D1-00-S01（本条用例是示例用例）

    测试用例名称：身份询问正常响应（冒烟示例）

    测试目标：
        验证 Agent 能够正常回答身份相关问题。

    前置条件：
        1. Agent CLI 已安装并完成登录。

    测试步骤：
        1. 启动 Agent 交互会话。
        2. 发送“你是谁？”。

    预期结果：
        1. 回复非空、语义连贯且正面说明身份或职责。
        2. 回复不含登录提示、报错或无关内容。
    """

    def test_agent_returns_identity_response(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.assert_agent_authenticated(agent_model, request)
        judge = self.require_judge_model(judge_model, request, agent_model)

        prompt = "你是谁？"
        turn = agent_model.send_prompt(prompt)
        self.assert_turn_completed(turn, request, agent_model)

        verdict = judge.evaluate(
            prompt=prompt,
            turn=turn,
            criterion=(
                "返回内容应当非空、语义连贯，并正面回答自己的身份或职责。"
                "登录提示、报错信息、无关内容或无法理解问题均判定为不通过。"
                "不要求返回特定产品名称。"
            ),
        )
        self.conclude_judge_verdict(verdict, request, agent_model)
