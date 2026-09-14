"""Mark TC-5.5b-D1-01 as requiring operator-controlled evidence."""

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.operator_evidence import OperatorEvidenceMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = "TC-5.5b-D1-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-5.5b-D1-01"
REPRESENTATIVE_CHILD_ID = "ATS-5.5b-D1-01-S01-01"
REPRESENTATIVE_CHILD_SCRIPT = "test_cases/test_cloud_log_retention_policy_and_cleanup_mechanism.py"
PRIORITY = "P3"
CATEGORY = "E"
IMPLEMENTATION_MODE = "deferred"
REQUIRED_CAPABILITY = "product_audit：需产品自身生成的真实过程记录；评测框架自记的请求日志不替代产品日志能力。"
EXECUTION_PROFILE = "product_audit"


OPERATOR_EVIDENCE_REQUIRED = True
OPERATOR_EVIDENCE_REQUIREMENT = (
    '访谈要求：本条指定负责人真实回答机制与绕过问题并形成确认记录；配套材料：真实设计存储配置与运维签字访谈；真实有效且不以材料替代当次动态测试；服务端要求：'
    '真实设计存储配置与运维签字访谈；真实有效且不以材料替代当次动态测试'
)


class TestTC55BD101P3Deferred(OperatorEvidenceMotherCaseRunner):
    """测试用例 ID：TC-5.5b-D1-01

    测试用例名称：云端日志留存机制与留存周期配置的存在性核查

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
        2. 需运营方提供：访谈要求：本条指定负责人真实回答机制与绕过问题并形成确认记录；配套材料：真实设计存储配置与运维签字访谈；真实有效且不以材料替代当次动态测试
           ；服务端要求：真实设计存储配置与运维签字访谈；真实有效且不以材料替代当次动态测试。
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
