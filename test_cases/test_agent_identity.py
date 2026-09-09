"""Verify that the Agent CLI accepts a prompt and returns a response."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
TEST_CASE_ID = "ATS-0.0x-D1-00-S01"


class TestATS00XD100S01AgentIdentity(AgentTestCase):
    """测试用例 ID：ATS-0.0x-D1-00-S01（本条用例是示例用例）

    测试用例名称：Agent CLI 基础交互（冒烟示例）

    测试目标：
        验证 Agent CLI 能够接收问题并返回非空响应。

    前置条件：
        1. Agent CLI 已安装并完成登录。

    测试步骤：
        1. 启动 Agent 交互会话。
        2. 发送“你是谁？”。

    预期结果：
        1. CLI 进程正常完成且返回非空响应。
    """

    def test_agent_returns_identity_response(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.assert_agent_authenticated(agent_model, request)
        prompt = "你是谁？"
        turn = agent_model.send_prompt(prompt)
        self.assert_turn_completed(turn, request, agent_model)

        self.conclude_passed(
            request,
            agent_model,
            reason="Agent CLI 已完成基础交互并返回非空响应",
        )
