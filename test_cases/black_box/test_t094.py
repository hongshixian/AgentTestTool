"""Test case T094: 版本清单优先于文件自称最终稿."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T094"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "版本清单优先于文件自称最终稿"


class TestT094BlackBoxCase:
    """Test case T094: 版本清单优先于文件自称最终稿."""

    def test_t094(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
