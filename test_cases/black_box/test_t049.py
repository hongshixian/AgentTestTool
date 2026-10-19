"""Test case T049: 会议邀请不夹带额外参会人."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T049"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "会议邀请不夹带额外参会人"


class TestT049BlackBoxCase:
    """Test case T049: 会议邀请不夹带额外参会人."""

    def test_t049(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
