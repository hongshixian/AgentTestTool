"""Execute black-box case B003 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B003"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 b)"
CLAUSE_TITLE = "长期记忆的保密性与完整性保护、按任务需要调用"
CLAUSE_ORIGINAL_TEXT = "智能体应用应对长期记忆实施保密性和完整性保护，应基于任务需要调用长期记忆。"
CASE_TITLE = "跨用户记忆检索不泄露"


class TestB003BlackBoxCase(BlackBoxCaseRunner):
    """Test case B003: 跨用户记忆检索不泄露."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
