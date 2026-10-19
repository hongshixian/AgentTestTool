"""Test case T052."""

import pytest
from test_cases.black_box.base import AgentTestCase
from test_cases.black_box.runner import BlackBoxCaseRunner

TEST_CASE_ID = "T052"
TEST_CASE_LEVEL = "black_box"


class TestT052BlackBoxCase(AgentTestCase, BlackBoxCaseRunner):
    """Test case T052: Black-box test."""

    def test_black_box_case(self, agent_model, tmp_path):
        """Execute black-box test case T052."""
        self.run_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            tmp_path=tmp_path,
        )
