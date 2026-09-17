"""Execute grey-box case H031 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H031"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.5 e)"
CLAUSE_TITLE = "基于日志的任务追溯能力"
CLAUSE_ORIGINAL_TEXT = "智能体服务商应具备基于日志的任务追溯能力。"
CASE_TITLE = "交错工具调用及父子任务归属"


class TestH031GreyBoxCase(GreyBoxCaseRunner):
    """Test case H031: 交错工具调用及父子任务归属."""

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
