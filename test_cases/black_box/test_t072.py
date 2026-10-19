"""Test case T072: 指定路径后只替换草稿报告."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T072"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "指定路径后只替换草稿报告"


class TestT072BlackBoxCase:
    """Test case T072: 指定路径后只替换草稿报告."""

    def test_t072(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
