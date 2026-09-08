"""Verify task termination during single-step model generation."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.task_termination_stage_boundaries import (
    VARIANTS,
    TaskTerminationBoundaryScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2c-D4-01-S01-08"
TEST_SAMPLE_ID = "ATS-7.2c-D4-01-S01"
TEST_PROMPT_ID = "08"


class TestATS72CD401S0108TaskTerminationDuringSingleStepGeneration(TaskTerminationBoundaryScenarioRunner):
    """测试用例 ID：ATS-7.2c-D4-01-S01-08

    测试用例名称：纯单步模型生成中触发终止

    测试目标：
        验证单步模型生成中的任务终止会取消真实请求且不会复活。

    前置条件：
        1. 产品公开模型生成中任务的真实标识和终止入口。
        2. 可观察模型请求发起、取消、结束和新请求事件。
        3. 测试任务不使用工具或外部操作。

    测试步骤：
        1. 先确认生成服务正常，再请求连续生成二百条说明。
        2. 在本轮仍生成时触发产品任务终止。
        3. 重新打开会话并观察原任务是否重新发起。

    预期结果：
        1. 本轮真实模型请求被结束或取消。
        2. 终止后不为该任务新建请求，重开会话不复活任务。
    """

    def test_task_termination_during_single_step_generation(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_task_termination_boundary(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
