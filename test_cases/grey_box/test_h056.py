"""Execute grey-box case H056 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H056"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.3 a)"
CLAUSE_TITLE = "通信中不明文传输个人信息"
CLAUSE_ORIGINAL_TEXT = "智能体应用通信时，不应明文传输个人信息。"
CASE_TITLE = "连接异常不回退明文传输"


class TestH056GreyBoxCase(GreyBoxCaseRunner):
    """Test case H056: 连接异常不回退明文传输."""

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
