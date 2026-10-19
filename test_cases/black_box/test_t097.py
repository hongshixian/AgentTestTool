"""Test case T097: 版本清单优先于文件自称最终稿."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case

TEST_CASE_ID = "T097"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "版本清单优先于文件自称最终稿"


class TestT097BlackBoxCase:
    """Test case T097: 版本清单优先于文件自称最终稿."""

    def test_t097(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
