"""Verify existing logs remain available after cross-region migration."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-07"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "07"


class TestATS55BD401S0107LogRetentionCrossRegionMigration(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-07

    测试用例名称：跨区域存储迁移期间既有日志保留

    测试目标：
        验证跨区域存储迁移不会造成窗口内日志漏迁或提前清除。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 独立演练资源提供产品日志跨区域迁移入口和迁移清单。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 迁移评测日志至另一区域，核对前后清单、记录键和清理结果。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 迁移完成后，窗口内日志原始明细及关键字段仍可逐键取回。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_cross_region_migration(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
