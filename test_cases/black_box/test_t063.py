"""Test case T063: 重命名任务保留负责人和附件."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T063"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "重命名任务保留负责人和附件"


class TestT063BlackBoxCase:
    """Test case T063: 重命名任务保留负责人和附件."""

    def test_t063(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
