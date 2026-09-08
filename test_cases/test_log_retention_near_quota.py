"""Verify existing logs remain available near the storage quota."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "01"


class TestATS55BD401S0101LogRetentionNearQuota(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-01

    测试用例名称：配额接近写满期间既有日志保留

    测试目标：
        验证存储配额接近写满时，六个月窗口内既有日志不会被提前清除。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 独立演练资源可预填充至实际配额接近上限，并可恢复。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 预填充存储后产生真实查询事件，记录占用、清理范围并逐键查询既有日志。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 达到演练占用后，窗口内日志的原始明细及关键字段仍可逐键取回。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_near_quota(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
