"""Verify inventory and material coverage for 备用降级模型."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_inventory_material_coverage import ModelInventoryMaterialCoverageScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D1-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.4b-D1-02-S01"
TEST_PROMPT_ID = "02"


class TestATS54BD102S0102FallbackModelMaterialCoverage(ModelInventoryMaterialCoverageScenarioRunner):
    """测试用例 ID：ATS-5.4b-D1-02-S01-02

    测试用例名称：备用降级模型清单与材料覆盖

    测试目标：
        验证备用降级模型均在清单中且证明材料匹配。

    前置条件：
        1. 降级路由可控，真实调用身份、配置及材料库可读取。

    测试步骤：
        1. 控制主模型超时并核对实际降级模型、清单和材料。

    预期结果：
        1. 每个向用户提供的降级模型均在册且材料匹配。
        2. 声称排除的模型经实测确未向用户提供。
    """

    def test_fallback_model_material_coverage(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_model_inventory_path(agent_model, request, model_kind="备用降级模型")
