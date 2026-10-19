"""Test case T168."""

import pytest
from test_cases.base import AgentTestCase
from test_cases.black_box.runner import BlackBoxCaseRunner

TEST_CASE_ID = "T168"
TEST_CASE_LEVEL = "black_box"


class TestT168BlackBoxCase(AgentTestCase, BlackBoxCaseRunner):
    """Test case T168: Black-box test."""

    def test_black_box_case(self, agent_model, tmp_path):
        """Execute black-box test case T168."""
        self.run_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            tmp_path=tmp_path,
        )
