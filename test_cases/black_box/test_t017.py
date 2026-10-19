"""Test case T017: 只批准一项时保留另一临时文件."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T017"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "只批准一项时保留另一临时文件"


class TestT017BlackBoxCase:
    """Test case T017: 只批准一项时保留另一临时文件."""

    def test_t017(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
