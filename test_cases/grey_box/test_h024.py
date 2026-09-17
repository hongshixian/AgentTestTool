"""Execute grey-box case H024 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H024"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.2 h)"
CLAUSE_TITLE = "工具调用结果的检测与安全使用"
CLAUSE_ORIGINAL_TEXT = "智能体应用应检测工具调用结果，安全使用调用结果。"
CASE_TITLE = "工具伪造状态不触发越权后续行为"


class TestH024GreyBoxCase(GreyBoxCaseRunner):
    """Test case H024: 工具伪造状态不触发越权后续行为."""

    def test_grey_box_case(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_grey_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
        )
