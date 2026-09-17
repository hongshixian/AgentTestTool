"""Execute grey-box case H051 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H051"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 c)"
CLAUSE_TITLE = "支持用户删除记忆"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户删除记忆。"
CASE_TITLE = "删除后模型请求不再携带旧记忆"


class TestH051GreyBoxCase(GreyBoxCaseRunner):
    """Test case H051: 删除后模型请求不再携带旧记忆."""

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
