"""Test case T140."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]

TEST_CASE_ID = "T140"
TEST_CASE_LEVEL = "black_box"


class TestT140BlackBoxCase(BlackBoxCaseRunner):
    """Test case T140: Black-box test."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        """Execute black-box test case T140."""
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
            judge_model=judge_model,
        )
