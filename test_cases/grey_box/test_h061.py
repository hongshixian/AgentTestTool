"""Execute grey-box case H061 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H061"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.1 c)"
CLAUSE_TITLE = "对输入方的追溯功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持对输入方的追溯功能。"
CASE_TITLE = "委托输入的调用方与原始发起方"


class TestH061GreyBoxCase(GreyBoxCaseRunner):
    """Test case H061: 委托输入的调用方与原始发起方."""

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
