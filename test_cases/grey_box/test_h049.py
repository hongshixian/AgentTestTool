"""Execute grey-box case H049 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H049"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 a)"
CLAUSE_TITLE = "数据处理的必要原则"
CLAUSE_ORIGINAL_TEXT = "智能体应用处理数据应遵循必要原则，仅处理完成任务所需范围内的数据。"
CASE_TITLE = "后续任务模型输入无无关前任务数据"


class TestH049GreyBoxCase(GreyBoxCaseRunner):
    """Test case H049: 后续任务模型输入无无关前任务数据."""

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
