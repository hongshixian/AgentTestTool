"""Execute grey-box case H059 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H059"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.3 c)"
CLAUSE_TITLE = "智能体间通信的完整性、机密性与抗重放"
CLAUSE_ORIGINAL_TEXT = "智能体应用间通信时，应使用具备完整性、机密性、抗重放性的安全通信机制。"
CASE_TITLE = "合法报文重复提交无重复副作用"


class TestH059GreyBoxCase(GreyBoxCaseRunner):
    """Test case H059: 合法报文重复提交无重复副作用."""

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
