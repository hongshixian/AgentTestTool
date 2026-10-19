"""Test case T090: 币种与单位按原始字段计算."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T090"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "币种与单位按原始字段计算"


class TestT090BlackBoxCase:
    """Test case T090: 币种与单位按原始字段计算."""

    def test_t090(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
