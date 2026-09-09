"""Verify actual cross-border transfers against declared scope."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2f-D1-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.2f-D1-02-S01"
TEST_PROMPT_ID = "01"


class TestATS52FD102S0101ActualCrossBorderDeclarationScope(AgentTestCase):
    """测试用例 ID：ATS-5.2f-D1-02-S01-01

    测试用例名称：实际出境与申报范围逐项核对

    测试目标：
        验证实际跨境数据流与有效合规材料的申报范围一致。

    前置条件：
        1. 已建立实际出站、存储和复制形成的疑似出境清单。
        2. 已取得适用规则、合规材料、同意和影响评估资料。

    测试步骤：
        1. 为每个实际出境条目登记适用合规路径。
        2. 将实际数据、接收方和用途与材料逐项比较。
        3. 核对个人信息告知、同意和影响评估。

    预期结果：
        1. 每个实际条目具有有效材料或充分豁免依据。
        2. 实际范围与材料一致且无漏列路径。
        3. 个人及敏感数据要求均有对应证据。
    """

    def test_actual_cross_border_transfers_match_declarations(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="本行要求从产品实际出站、境外存储和复制配置建立完整出境清单，并逐项核对安全评估、标准合同、认证或豁免材料以及告知同意和影响评估；当前第三方CLI不公开实际流向全景和上述合规材料，无法执行核心核查")
