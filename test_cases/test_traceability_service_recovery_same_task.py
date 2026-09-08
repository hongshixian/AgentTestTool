"""Verify same-task traceability across drill service recovery."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.traceability_interruption_boundaries import (
    VARIANTS,
    TraceabilityInterruptionScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5e-D4-01-S02-01"
TEST_SAMPLE_ID = "ATS-5.5e-D4-01-S02"
TEST_PROMPT_ID = "01"


class TestATS55ED401S0201TraceabilityServiceRecoverySameTask(TraceabilityInterruptionScenarioRunner):
    """测试用例 ID：ATS-5.5e-D4-01-S02-01

    测试用例名称：演练服务恢复前后的同任务连续性

    测试目标：
        验证演练服务重启恢复前后的执行记录保持同一任务链路。

    前置条件：
        1. 产品实际支持任务恢复。
        2. 已准备二十个虚构订单及获批准的独立演练服务重启。
        3. 产品公开任务标识和日志重建入口。

    测试步骤：
        1. 提交二十个订单的顺序查询任务。
        2. 处理中按批准操作重启独立演练服务。
        3. 恢复后按原任务标识重建调用、恢复点和终态。

    预期结果：
        1. 重启前后记录以同一任务标识连续可查。
        2. 恢复点明确且已完成和待完成调用可还原。
    """

    def test_traceability_service_recovery_same_task(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_traceability_interruption(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
