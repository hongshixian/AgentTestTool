"""Execute black-box case B011 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B011"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 a)"
CLAUSE_TITLE = "实例唯一身份标识与安全责任主体关联"
CLAUSE_ORIGINAL_TEXT = "智能体应用实例应具备唯一身份标识，该身份标识可用于识别、关联智能体应用安全责任主体。"
CASE_TITLE = "公开实例创建后的标识唯一性"


class TestB011BlackBoxCase(BlackBoxCaseRunner):
    """Test case B011: 公开实例创建后的标识唯一性."""

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
