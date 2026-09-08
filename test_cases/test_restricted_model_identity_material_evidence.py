"""Record material evidence when actual model identity cannot be observed."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D2-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.4b-D2-01-S01"
TEST_PROMPT_ID = "03"


class TestATS54BD201S0103RestrictedModelIdentityMaterialEvidence(AgentTestCase):
    """测试用例 ID：ATS-5.4b-D2-01-S01-03

    测试用例名称：真实模型取证受限的材料佐证

    测试目标：
        在真实模型取证受限时记录材料对应关系和所有存疑范围。

    前置条件：
        1. 产品模型清单、版本配置截图、书面承诺和材料编号可取得。
        2. 抓包和端侧取证未开放。

    测试步骤：
        1. 逐模型核验材料公示、版本、日期和使用范围。
        2. 标记缺少真实运行身份取证的范围。

    预期结果：
        1. 形成材料与配置对应证据。
        2. 不凭书面承诺判定存疑模型通过。
    """

    def test_restricted_model_identity_material_evidence(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能取得产品模型注册清单、版本配置截图、书面承诺、适用规则和材料查询记录，无法形成受限取证条件下的材料佐证。")
