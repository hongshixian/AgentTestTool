"""Execute black-box case B017 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B017"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 c)"
CLAUSE_TITLE = "支持用户删除记忆"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户删除记忆。"
CASE_TITLE = "清除会话后的用户可见上下文"


class TestB017BlackBoxCase(BlackBoxCaseRunner):
    """Test case B017: 清除会话后的用户可见上下文."""

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
