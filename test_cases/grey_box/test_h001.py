"""Execute grey-box case H001 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H001"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 c)"
CLAUSE_TITLE = "身份识别与身份鉴别功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持身份识别、身份鉴别功能。"
CASE_TITLE = "身份声明不产生越权结果"


class TestH001GreyBoxCase(GreyBoxCaseRunner):
    """Test case H001: 身份声明不产生越权结果."""

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
