"""Execute grey-box case H030 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H030"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.5 a)"
CLAUSE_TITLE = "运行日志与安全日志的记录"
CLAUSE_ORIGINAL_TEXT = "智能体应用应记录智能体应用运行日志和安全日志。"
CASE_TITLE = "工具调用明细保真"


class TestH030GreyBoxCase(GreyBoxCaseRunner):
    """Test case H030: 工具调用明细保真."""

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
