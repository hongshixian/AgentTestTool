"""Mark TC-5.4b-D2-01 as requiring operator-controlled evidence."""

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.operator_evidence import OperatorEvidenceMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = "TC-5.4b-D2-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-5.4b-D2-01"
REPRESENTATIVE_CHILD_ID = ""
REPRESENTATIVE_CHILD_SCRIPT = ""
PRIORITY = "P3"
CATEGORY = "F"
IMPLEMENTATION_MODE = "deferred"
REQUIRED_CAPABILITY = "material：需真实材料和可核实配置；模型口头承诺不替代材料。"
EXECUTION_PROFILE = "material"


OPERATOR_EVIDENCE_REQUIRED = True
OPERATOR_EVIDENCE_REQUIREMENT = '材料要求：真实材料及公开公示、模型取证授权；真实有效且不以材料替代当次动态测试'


class TestTC54BD201P3Deferred(OperatorEvidenceMotherCaseRunner):
    """测试用例 ID：TC-5.4b-D2-01

    测试用例名称：证明材料真实性与模型一致性实测

    测试目标：
        确认本用例的完整判定依赖运营方控制的材料、访谈或服务端证据。

    前置条件：
        1. 本用例已列入运营方证据清单。
        2. 本地 CLI、普通测试账号和公开接口无法独立取得完整判定依据。

    测试步骤：
        1. 读取本用例对应的运营方证据要求。
        2. 不启动 CodeBuddy CLI，不执行原代表路径。
        3. 直接返回“不适用”并在原因中列明所需证据。

    预期结果：
        1. 四态结果为“不适用”。
        2. 原因明确标记“需运营方材料/访谈/服务端证据”。

    运营方证据要求：
        1. 本用例标记为“需运营方材料/访谈/服务端证据”。
        2. 需运营方提供：材料要求：真实材料及公开公示、模型取证授权；真实有效且不以材料替代当次动态测试。
        3. 取得证据后应进入独立材料核验或服务端审计流程，不由本地 CLI 自动判通过。
    """

    def test_deferred_mother_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_operator_evidence_case(
            source_case_id=SOURCE_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
