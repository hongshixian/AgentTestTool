"""Execute black-box case B018 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B018"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 c)"
CLAUSE_TITLE = "支持用户删除记忆"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户删除记忆。"
CASE_TITLE = "删除请求异常后的幂等与状态一致"


class TestB018BlackBoxCase(BlackBoxCaseRunner):
    """Test case B018: 删除请求异常后的幂等与状态一致."""

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
