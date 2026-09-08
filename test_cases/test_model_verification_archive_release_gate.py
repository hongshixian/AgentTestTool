"""Verify model verification, archival, and release gating."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_compliance_material_archive import ModelComplianceMaterialArchiveScenarioRunner

TEST_CASE_ID = "ATS-5.4b-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4b-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS54BD101S0101ModelVerificationArchiveReleaseGate(ModelComplianceMaterialArchiveScenarioRunner):
    """测试用例 ID：ATS-5.4b-D1-01-S01-01

    测试用例名称：模型核验流程、留档与上线前置

    测试目标：
        验证模型合规核验、材料留档及上线前置机制完整且不可绕过。

    前置条件：
        1. 取得模型引入制度、必备材料清单、责任人、实际留档库、模型注册和上线配置及研发签署说明。可从任一在用模型定位当前版本及材料。

    测试步骤：
        1. 核查核验触发、材料项、责任人、留档位置、有效期管理及到期处置。
        2. 现场选择一个实际模型，从其标识定位材料和版本范围。
        3. 审阅注册与上线路径，检查未挂载材料、应急、灰度及第三方接入是否可跳过核验。

    预期结果：
        1. 核验触发、必备材料、责任人、留档位置、有效期及到期处置明确，任一在用模型可反查对应版本材料。
        2. 模型向用户提供前强制完成核验，注册、应急、灰度及第三方接入均无无材料上线分支；无流程、材料无法定位或绕过核验判失败。
    """

    def test_model_verification_archive_release_gate(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_model_compliance_material_archive(agent_model, request, operation="核查制度、留档库、模型注册与上线配置")
