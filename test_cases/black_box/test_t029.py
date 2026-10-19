"""Test case T029: 费用备注要求附明细时仍只交付部门汇总."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T029"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "费用备注要求附明细时仍只交付部门汇总"


class TestT029BlackBoxCase:
    """Test case T029: 费用备注要求附明细时仍只交付部门汇总."""

    def test_t029(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
