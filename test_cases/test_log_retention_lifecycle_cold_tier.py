"""Verify existing logs remain available across lifecycle and tiering changes."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-08"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "08"


class TestATS55BD401S0108LogRetentionLifecycleColdTier(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-08

    测试用例名称：生命周期规则变更及冷热转换期间既有日志保留

    测试目标：
        验证生命周期规则变更和冷热转换不会造成窗口内日志丢失。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 独立演练资源提供生命周期规则变更、冷热转换和恢复入口。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 按计划变更生命周期规则并执行冷热转换，核对清单、旧副本清理和可恢复性。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 变更和转换完成后，窗口内日志原始明细及关键字段仍可逐键取回。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_lifecycle_cold_tier(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
