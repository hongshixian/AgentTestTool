"""Execute grey-box case H046 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H046"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 c)"
CLAUSE_TITLE = "身份识别与身份鉴别功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持身份识别、身份鉴别功能。"
CASE_TITLE = "双向鉴别中的凭证实际使用"


class TestH046GreyBoxCase(GreyBoxCaseRunner):
    """Test case H046: 双向鉴别中的凭证实际使用."""

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
