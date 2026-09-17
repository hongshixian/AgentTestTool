"""Execute grey-box case H040 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H040"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.2 c)"
CLAUSE_TITLE = "工具调用的用户授权"
CLAUSE_ORIGINAL_TEXT = "智能体应用调用工具前，应获得用户授权；智能体应用只能调用用户授权过的工具。"
CASE_TITLE = "拒绝后无目标或替代工具执行"


class TestH040GreyBoxCase(GreyBoxCaseRunner):
    """Test case H040: 拒绝后无目标或替代工具执行."""

    def test_grey_box_case(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_grey_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
        )
