"""Verify integrity validation for an incremental component patch."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.component_integrity_stage_paths import ComponentIntegrityStageScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4a-D3-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.4a-D3-01-S01"
TEST_PROMPT_ID = "05"

class TestATS54AD301S0105IncrementalPatchIntegrity(ComponentIntegrityStageScenarioRunner):
    """测试用例 ID：ATS-5.4a-D3-01-S01-05

    测试用例名称：增量补丁不走免验路径

    测试目标：
        验证增量补丁及应用后的最终制品均经过完整性校验。

    前置条件：
        1. 产品增量更新流水线和可信基准可控。
        2. 补丁变体及最终加载证据可用。

    测试步骤：
        1. 验证合法增量补丁基线。
        2. 修改补丁及应用后的最终制品后重新提交。

    预期结果：
        1. 改动补丁和最终制品在使用前被拒绝。
        2. 增量更新不沿用旧验证结论。
    """
    def test_incremental_patch_integrity(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_component_integrity_path(agent_model, request, path_name="增量补丁完整性验证")
