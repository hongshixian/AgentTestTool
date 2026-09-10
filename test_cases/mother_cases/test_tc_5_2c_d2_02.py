"""Run one P2 representative path for mother case TC-5.2c-D2-02."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.mother_cases.p2_output import P2OutputMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.security, pytest.mark.mother_case]
TEST_CASE_ID = "TC-5.2c-D2-02"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-5.2c-D2-02"
REPRESENTATIVE_CHILD_ID = "ATS-5.2c-D2-02-S02-01"
REPRESENTATIVE_CHILD_SCRIPT = "test_cases/test_memory_clear_semantic_recall.py"
PRIORITY = "P2"
CATEGORY = "J"
IMPLEMENTATION_MODE = "p2_output"


class TestTC52CD202P2MotherCase(P2OutputMotherCaseRunner):
    """测试用例 ID：TC-5.2c-D2-02

    测试用例名称：整体清空与账号注销后的记忆清除实测

    测试目标：
        按 CLI 宽松判定版 v3 执行一条语义有效的最简代表路径。

    前置条件：
        1. 被测 Agent 具备本条路径要求的真实公开能力。
        2. 仅使用第三方可观察的 CLI、工具或产品状态证据。

    测试步骤：
        1. 建立本条母用例所需的独立受控事实。
        2. 执行真实代表路径并采集用户可见结果。
        3. 仅按 v3 明确失败事实作宽松判定。

    预期结果：
        1. 命中明确失败事实时判定不通过。
        2. 缺少必要公开能力时明确判定不适用。
    """

    def test_p2_output_path(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_p2_output_case(
            source_case_id=SOURCE_CASE_ID,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
        )
