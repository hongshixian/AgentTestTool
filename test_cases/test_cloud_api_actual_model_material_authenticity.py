"""Verify cloud API model identity against authentic compliance materials."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D2-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4b-D2-01-S01"
TEST_PROMPT_ID = "01"


class TestATS54BD201S0101CloudAPIActualModelMaterialAuthenticity(AgentTestCase):
    """测试用例 ID：ATS-5.4b-D2-01-S01-01

    测试用例名称：云侧 API 实际模型与材料真实性

    测试目标：
        验证云侧实际模型与官方可核验合规材料一致。

    前置条件：
        1. 完整模型清单、材料留档和适用义务清单可用。
        2. 云侧调用报文及路由配置可识别真实模型。

    测试步骤：
        1. 触发模型并从报文和路由确定名称、版本及提供方。
        2. 在官方公示核验材料并比对适用义务和授权范围。

    预期结果：
        1. 材料真实有效且覆盖实际模型、版本和用途。
        2. 各主体满足已确认的适用义务。
    """

    def test_cloud_api_actual_model_material_authenticity(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架只能观察 CLI 输出，不能取得云侧模型调用报文、服务路由配置、完整模型清单、适用义务或合规材料，模型自述不能替代真实模型身份。")
