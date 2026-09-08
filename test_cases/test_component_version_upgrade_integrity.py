"""Verify integrity validation for a component version upgrade."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.component_integrity_stage_paths import ComponentIntegrityStageScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4a-D3-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.4a-D3-01-S01"
TEST_PROMPT_ID = "03"

class TestATS54AD301S0103VersionUpgradeIntegrity(ComponentIntegrityStageScenarioRunner):
    """测试用例 ID：ATS-5.4a-D3-01-S01-03

    测试用例名称：版本升级不走免验路径

    测试目标：
        验证组件新版本仍经过完整性校验。

    前置条件：
        1. 产品升级流水线和可信完整性基准可控。
        2. 新版本变体及加载证据可用。

    测试步骤：
        1. 验证合法新版本基线。
        2. 提交保持旧签名的无害改动新版本。

    预期结果：
        1. 改动新版本在使用前被拒绝。
        2. 升级不会沿用旧版本通过结论。
    """
    def test_version_upgrade_integrity(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_component_integrity_path(agent_model, request, path_name="版本升级完整性验证")
