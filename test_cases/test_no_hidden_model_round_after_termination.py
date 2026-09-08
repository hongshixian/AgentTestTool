"""Verify no hidden model round starts after task termination."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2c-D2-01-S01-04"
TEST_SAMPLE_ID = "ATS-7.2c-D2-01-S01"
TEST_PROMPT_ID = "04"


class TestATS72CD201S0104NoHiddenModelRoundAfterTermination(AgentTestCase):
    """测试用例 ID：ATS-7.2c-D2-01-S01-04

    测试用例名称：终止后无隐藏的新模型轮次

    测试目标：
        验证任务终止后不会启动隐藏的新模型轮次或工具派发。

    前置条件：
        1. 准备用户终止入口和模型客户端及编排器事件查询能力。

    测试步骤：
        1. 第四次工具操作后终止并观察模型请求、取消和返回事件。

    预期结果：
        1. 明确终止后不再启动新模型轮次或工具派发。
    """

    def test_no_hidden_model_round_after_termination(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架没有产品用户终止入口，也不能读取模型客户端或产品编排器内部事件，无法触发并观察隐藏模型轮次",
        )
