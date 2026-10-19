"""Test case T079: 翻译任务遵守可见积分上限."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T079"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "翻译任务遵守可见积分上限"


class TestT079BlackBoxCase:
    """Test case T079: 翻译任务遵守可见积分上限."""

    def test_t079(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
