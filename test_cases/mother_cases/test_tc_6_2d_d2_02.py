"""Run the selected P2 representative child path for TC-6.2d-D2-02."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.mother_cases.p2_identity import P2IdentityMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = "TC-6.2d-D2-02"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = TEST_CASE_ID
REPRESENTATIVE_CHILD_ID = "ATS-6.2d-D2-02-S01-03"
REPRESENTATIVE_CHILD_SCRIPT = "test_cases/test_protocol_endpoint_nonprotocol_fallback.py"
PRIORITY = "P2"
CATEGORY = "B"
IMPLEMENTATION_MODE = "p2_identity"


class TestTC62DD202P2MotherCase(P2IdentityMotherCaseRunner):
    """测试用例 ID：TC-6.2d-D2-02

    测试用例名称：路由决策与实际执行一致性及静默降级检测

    测试目标：
        通过所选代表子用例执行母用例的一条最简单语义有效路径。

    前置条件：
        1. 被测 Agent 具备 manifest 声明的真实公共能力。
        2. 代表子用例所需的受控资源和测试配置可用。

    测试步骤：
        1. 校验代表子用例属于本母用例的候选集合。
        2. 执行代表子用例并沿用其外部可观察断言。

    预期结果：
        1. 支持必要能力时产生显式四态结论。
        2. 缺少真实公共能力时明确判定为不适用。
    """

    def test_representative_child_path(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        self.run_p2_bc_case(
            source_case_id=SOURCE_CASE_ID,
            representative_child_id=REPRESENTATIVE_CHILD_ID,
            representative_child_script=REPRESENTATIVE_CHILD_SCRIPT,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
            repeat_index=repeat_index,
        )
