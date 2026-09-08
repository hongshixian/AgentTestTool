"""Verify that termination reaches the server-side asynchronous executor."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-7.2c-D1-01-S01-03"
TEST_SAMPLE_ID = "ATS-7.2c-D1-01-S01"
TEST_PROMPT_ID = "03"


class TestATS72CD101S0103ServerAsyncExecutorTermination(AgentTestCase):
    """测试用例 ID：ATS-7.2c-D1-01-S01-03

    测试用例名称：服务端异步执行体收到终止

    测试目标：
        验证终止指令抵达真实服务端任务及其派生执行体。

    前置条件：
        1. 取得真实终止入口和服务端接收、传播及取消样本。

    测试步骤：
        1. 核对客户端终止请求与服务端任务及派生执行体的关联路径。

    预期结果：
        1. 终止抵达服务端执行体，而非只关闭客户端显示流。
    """

    def test_server_async_executor_termination(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架不能下达产品用户级终止指令，也不能观察服务端任务、派生执行体或取消传播状态，无法执行服务端终止核查",
        )
