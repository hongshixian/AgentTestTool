"""Test case T032: 会议摘要按允许字段去掉私人联系信息."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.runner import run_black_box_case


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T032"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = ""
STANDARD_CLAUSE = ""
CLAUSE_TITLE = ""
CLAUSE_ORIGINAL_TEXT = ""
CASE_TITLE = "会议摘要按允许字段去掉私人联系信息"


class TestT032BlackBoxCase:
    """Test case T032: 会议摘要按允许字段去掉私人联系信息."""

    def test_t032(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> None:
        run_black_box_case(TEST_CASE_ID, agent_model, request)
