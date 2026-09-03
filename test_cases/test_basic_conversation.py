"""Product-neutral basic conversation cases."""

import pytest

from agent_models import AgentModel
from judge import OpenAICompatibleJudge


pytestmark = pytest.mark.e2e


def test_agent_returns_a_normal_identity_response(
    agent_model: AgentModel,
    judge_model: OpenAICompatibleJudge,
) -> None:
    authentication = agent_model.check_authentication()
    assert authentication.authenticated, authentication.detail

    prompt = "你是谁？"
    turn = agent_model.send_prompt(prompt)
    assert turn.completed, turn.stderr or turn.raw_output[-1000:]

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

