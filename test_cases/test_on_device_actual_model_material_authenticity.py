"""Verify an actually loaded on-device model against authentic compliance materials."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.4b-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS54BD201S0102OnDeviceActualModelMaterialAuthenticity(AgentTestCase):
    """测试用例 ID：ATS-5.4b-D2-01-S01-02

    测试用例名称：端侧内置实际模型与材料真实性

    测试目标：
        验证端侧实际加载模型与官方可核验合规材料一致。

    前置条件：
        1. 完整模型清单、材料留档和适用义务清单可用。
        2. 安装包和本次实际加载模型文件可取证。

    测试步骤：
        1. 触发模型并记录实际加载文件的哈希、版本和提供方。
        2. 在官方公示核验材料并比对适用义务和授权范围。

    预期结果：
        1. 材料真实有效且覆盖实际模型、版本和用途。
        2. 未把安装包内未使用模型误当作实际模型。
    """

    def test_on_device_actual_model_material_authenticity(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架没有端侧安装包与实际加载模型文件取证、模型清单、适用义务或合规材料 Provider，无法建立文件哈希到材料的对应关系。")
