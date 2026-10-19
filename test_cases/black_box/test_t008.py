"""Execute black-box case T008 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T008"
TEST_CASE_LEVEL = "black_box"


class TestT008BlackBoxCase(BlackBoxCaseRunner):
    """Test case T008: Black-box test."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        """Execute black-box test case T008."""
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
