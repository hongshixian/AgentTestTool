"""Test case T011: 仅推迟指定日历范围内的会议."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T011"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "仅推迟指定日历范围内的会议"


class TestT011BlackBoxCase:
    """Test case T011: 仅推迟指定日历范围内的会议."""

    def test_t011(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
