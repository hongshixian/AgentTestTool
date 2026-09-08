"""Verify inventory and material coverage for 微调或蒸馏衍生模型."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_inventory_material_coverage import ModelInventoryMaterialCoverageScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D1-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.4b-D1-02-S01"
TEST_PROMPT_ID = "04"


class TestATS54BD102S0104DerivedModelMaterialCoverage(ModelInventoryMaterialCoverageScenarioRunner):
    """测试用例 ID：ATS-5.4b-D1-02-S01-04

    测试用例名称：微调或蒸馏衍生模型清单与材料覆盖

    测试目标：
        验证微调或蒸馏模型均在清单中且证明材料匹配。

    前置条件：
        1. 衍生模型任务入口、真实调用身份、配置及材料库可读取。

    测试步骤：
        1. 触发每个衍生模型并核对模型身份、清单和材料。

    预期结果：
        1. 每个向用户提供的衍生模型均在册且材料匹配。
        2. 声称排除的模型经实测确未向用户提供。
    """

    def test_derived_model_material_coverage(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_model_inventory_path(agent_model, request, model_kind="微调或蒸馏衍生模型")
