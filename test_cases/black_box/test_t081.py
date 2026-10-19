"""Test case T081: 保存状态与实际文件一致."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T081"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "保存状态与实际文件一致"


class TestT081BlackBoxCase:
    """Test case T081: 保存状态与实际文件一致."""

    def test_t081(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
