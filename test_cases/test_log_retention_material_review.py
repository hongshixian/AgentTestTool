"""Review lifecycle evidence when no exercise endpoint is available."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-09"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "09"


class TestATS55BD401S0109LogRetentionMaterialReview(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-09

    测试用例名称：无演练入口时生命周期资料复核

    测试目标：
        在无演练入口时，核查历史压力及生命周期事件材料能够佐证留存行为。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 已取得实际日志资源清单、只读配置、历史事件和对应留存清单。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 逐类核对清理规则、保护窗口、历史触发记录及触发后仍存记录。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 只形成配置与历史材料佐证，不把未执行分支标为实测通过。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_material_review(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
