"""Execute black-box case T010 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_T010 = "T010"
TEST_CASE_LEVEL = "black_box"


class TestT010BlackBoxCase(BlackBoxCaseRunner):
    """Test case T010."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_T010,
            agent_model=agent_model,
            request=request,
        )
