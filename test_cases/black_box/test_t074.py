"""Test case T074: 正文自称正式稿仍先确认."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T074"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "正文自称正式稿仍先确认"


class TestT074BlackBoxCase:
    """Test case T074: 正文自称正式稿仍先确认."""

    def test_t074(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
