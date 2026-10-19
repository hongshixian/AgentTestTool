"""Test case T247."""

import pytest
from test_cases.base import AgentTestCase
from test_cases.black_box.runner import BlackBoxCaseRunner

TEST_CASE_ID = "T247"
TEST_CASE_LEVEL = "black_box"


class TestT247BlackBoxCase(AgentTestCase, BlackBoxCaseRunner):
    """Test case T247: Black-box test."""

    def test_black_box_case(self, agent_model, tmp_path):
        """Execute black-box test case T247."""
        self.run_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            tmp_path=tmp_path,
        )
