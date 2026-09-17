"""Execute black-box case B001 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B001"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 c)"
CLAUSE_TITLE = "身份识别与身份鉴别功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持身份识别、身份鉴别功能。"
CASE_TITLE = "凭据正反向与身份绑定"


class TestB001BlackBoxCase(BlackBoxCaseRunner):
    """Test case B001: 凭据正反向与身份绑定."""

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
