"""Execute black-box case T007 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_T007 = "T007"
TEST_CASE_LEVEL = "black_box"


class TestT007BlackBoxCase(BlackBoxCaseRunner):
    """Test case T007."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_T007,
            agent_model=agent_model,
            request=request,
        )
