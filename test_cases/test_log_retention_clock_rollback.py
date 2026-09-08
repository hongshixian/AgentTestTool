"""Verify existing logs remain available after cleanup clock rollback."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "05"


class TestATS55BD401S0105LogRetentionClockRollback(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-05

    测试用例名称：时钟回拨期间既有日志保留

    测试目标：
        验证清理组件时钟回拨不会导致窗口内日志被误判超期。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 演练环境允许记录可信时钟、回拨清理组件时钟并执行正常清理作业。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 回拨清理组件时钟并触发作业，保存实际截止时间并逐键查询日志。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 时钟回拨且清理作业执行后，窗口内日志仍可逐键取回。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_clock_rollback(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
