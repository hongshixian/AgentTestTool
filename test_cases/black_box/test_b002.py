"""Execute black-box case B002 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B002"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 c)"
CLAUSE_TITLE = "身份识别与身份鉴别功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持身份识别、身份鉴别功能。"
CASE_TITLE = "注销后旧凭证失效"


class TestB002BlackBoxCase(BlackBoxCaseRunner):
    """Test case B002: 注销后旧凭证失效."""

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
