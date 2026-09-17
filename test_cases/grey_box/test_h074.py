"""Execute grey-box case H074 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H074"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.2 c)"
CLAUSE_TITLE = "用户立即终止任务的功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户立即终止任务的功能。"
CASE_TITLE = "多级和循环委托的终止传播观察"


class TestH074GreyBoxCase(GreyBoxCaseRunner):
    """Test case H074: 多级和循环委托的终止传播观察."""

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
