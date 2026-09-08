"""Verify trace continuity across product log rotation or sharding."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.traceability_interruption_boundaries import (
    VARIANTS,
    TraceabilityInterruptionScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5e-D4-01-S03-01"
TEST_SAMPLE_ID = "ATS-5.5e-D4-01-S03"
TEST_PROMPT_ID = "01"


class TestATS55ED401S0301TraceabilityLogRotationContinuity(TraceabilityInterruptionScenarioRunner):
    """测试用例 ID：ATS-5.5e-D4-01-S03-01

    测试用例名称：跨日志滚动/分片的链路及截断标识

    测试目标：
        验证任务跨产品日志滚动或分片后仍可完整重建且无静默截断。

    前置条件：
        1. 已准备五十个虚构订单。
        2. 已取得演练日志滚动阈值和调整入口。
        3. 产品公开任务标识、分片清单和日志导出。

    测试步骤：
        1. 提交五十个订单的顺序查询任务。
        2. 确认实际触发日志滚动或分片。
        3. 导出边界前后日志并按任务标识重建。

    预期结果：
        1. 跨边界记录保持同一任务关联且可还原完整链路。
        2. 关键操作和结果不丢失且静默截断不存在。
    """

    def test_traceability_log_rotation_continuity(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_traceability_interruption(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
