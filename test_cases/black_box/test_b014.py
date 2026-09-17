"""Execute black-box case B014 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B014"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 c)"
CLAUSE_TITLE = "身份识别与身份鉴别功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持身份识别、身份鉴别功能。"
CASE_TITLE = "受保护业务入口的未鉴别访问拒绝"


class TestB014BlackBoxCase(BlackBoxCaseRunner):
    """Test case B014: 受保护业务入口的未鉴别访问拒绝."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
