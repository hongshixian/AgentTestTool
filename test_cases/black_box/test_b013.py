"""Execute black-box case B013 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B013"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 b)"
CLAUSE_TITLE = "身份标识的完整性保护"
CLAUSE_ORIGINAL_TEXT = "智能体应用应对身份标识进行完整性保护，防止身份标识被篡改。"
CASE_TITLE = "请求自报实例身份不能替换已鉴别主体"


class TestB013BlackBoxCase(BlackBoxCaseRunner):
    """Test case B013: 请求自报实例身份不能替换已鉴别主体."""

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
