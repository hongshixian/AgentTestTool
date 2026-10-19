"""Execute black-box case T003 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_T003 = "T003"
TEST_CASE_LEVEL = "black_box"


class TestT003BlackBoxCase(BlackBoxCaseRunner):
    """Test case T003."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_T003,
            agent_model=agent_model,
            request=request,
        )
