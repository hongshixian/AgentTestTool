"""Execute black-box case B005 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B005"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.1 b)"
CLAUSE_TITLE = "输入安全检测与防护能力"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持输入安全检测与防护能力。"
CASE_TITLE = "直接注入不修改禁止任务文件"


class TestB005BlackBoxCase(BlackBoxCaseRunner):
    """Test case B005: 直接注入不修改禁止任务文件."""

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
