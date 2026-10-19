"""Execute black-box case T004 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_T004 = "T004"
TEST_CASE_LEVEL = "black_box"


class TestT004BlackBoxCase(BlackBoxCaseRunner):
    """Test case T004."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_T004,
            agent_model=agent_model,
            request=request,
        )
