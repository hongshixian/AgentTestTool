"""Verify that the Agent returns a normal identity response."""

import pytest

from agent_models import AgentModel
from judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase


pytestmark = pytest.mark.e2e


class TestATC001AgentIdentity(AgentTestCase):
    """测试用例 ID：ATC-001

    测试用例名称：Agent 身份信息正常返回

    测试目标：
        验证 Agent 能够正常回答身份相关问题。

    前置条件：
        1. 被测 Agent CLI 已安装。
        2. 被测 Agent 已完成登录认证。
        3. Judge 模型 API 配置可用。

    测试步骤：
        1. 初始化被测 Agent Model。
        2. 检查 Agent 登录状态。
        3. 向 Agent 发送“你是谁？”。
        4. 使用 Judge 模型评价 Agent 返回。
        5. 断言 Judge 判定结果为通过。

    预期结果：
        1. Agent 返回非空且语义连贯的身份说明。
        2. 返回内容不是登录提示、错误信息或无关内容。
        3. Judge 模型判定该返回通过。
    """

    def test_agent_returns_identity_response(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge,
    ) -> None:
        self.assert_agent_authenticated(agent_model)

        prompt = "你是谁？"
        turn = agent_model.send_prompt(prompt)
        self.assert_turn_completed(turn)

        verdict = judge_model.evaluate(
            prompt=prompt,
            turn=turn,
            criterion=(
                "返回内容应当非空、语义连贯，并正面回答自己的身份或职责。"
                "登录提示、报错信息、无关内容或无法理解问题均判定为不通过。"
                "不要求返回特定产品名称。"
            ),
        )
        assert verdict.passed, verdict.reason

