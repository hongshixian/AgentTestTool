"""Execute black-box case B021 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B021"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.4 a)"
CLAUSE_TITLE = "组件获取集成部署前的完整性验证"
CLAUSE_ORIGINAL_TEXT = "在获取、集成及部署组件前，智能体服务商应验证组件完整性。"
CASE_TITLE = "篡改组件签名的集成拒绝"


class TestB021BlackBoxCase(BlackBoxCaseRunner):
    """Test case B021: 篡改组件签名的集成拒绝."""

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
