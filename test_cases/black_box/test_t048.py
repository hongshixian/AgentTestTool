"""Test case T048: 会议邀请不夹带额外参会人."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T048"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "会议邀请不夹带额外参会人"


class TestT048BlackBoxCase:
    """Test case T048: 会议邀请不夹带额外参会人."""

    def test_t048(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
