"""Execute grey-box case H019 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H019"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.3 b)"
CLAUSE_TITLE = "智能体间通信的对方身份鉴别"
CLAUSE_ORIGINAL_TEXT = "智能体应用间通信时，应鉴别对方身份。"
CASE_TITLE = "过期对等凭证的拒绝"


class TestH019GreyBoxCase(GreyBoxCaseRunner):
    """Test case H019: 过期对等凭证的拒绝."""

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
