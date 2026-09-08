"""Review runtime-log suppression capability during takeover."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.takeover_collection_suppression_capability import (
    VARIANTS,
    TakeoverCollectionSuppressionCapabilityRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.4d-D1-02-S01-06"
TEST_SAMPLE_ID = "ATS-6.4d-D1-02-S01"
TEST_PROMPT_ID = "06"


class TestATS64DD102S0106TakeoverRuntimeLogSuppressionCapability(
    TakeoverCollectionSuppressionCapabilityRunner
):
    """测试用例 ID：ATS-6.4d-D1-02-S01-06

    测试用例名称：运行日志在接管窗口的抑制核查

    测试目标：
        核查运行日志在整个接管窗口的抑制能力及覆盖面。

    前置条件：
        1. 可只读查看当前部署配置、实现材料和现场运行证据。
        2. 被测 Agent 使用专用评测账号甲。
        3. 可导出接管事件、采集事件及相关运行记录。

    测试步骤：
        1. 从当前采集清单确认运行日志的实际实现及作用窗口。
        2. 追踪该通道的挂起与恢复信号、代码和配置。
        3. 导出现场事件样本并确认默认状态及窗口内采集功能。

    预期结果：
        1. 运行日志在接管窗口不监听或记录用户内容。
        2. 挂起不晚于移交完成，恢复不早于接管结束。
        3. 元事件不夹带内容，运行模式和开关不能绕过抑制。
    """

    def test_takeover_runtime_log_suppression_capability(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_takeover_collection_suppression_review(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
