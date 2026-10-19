"""Test case T024: 拒绝后继续处理不恢复发送授权."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T024"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "拒绝后继续处理不恢复发送授权"


class TestT024BlackBoxCase:
    """Test case T024: 拒绝后继续处理不恢复发送授权."""

    def test_t024(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
