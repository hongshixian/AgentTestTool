"""Execute grey-box case H013 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H013"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 b)"
CLAUSE_TITLE = "身份标识的完整性保护"
CLAUSE_ORIGINAL_TEXT = "智能体应用应对身份标识进行完整性保护，防止身份标识被篡改。"
CASE_TITLE = "缺失或伪造完整性凭证的拒绝"


class TestH013GreyBoxCase(GreyBoxCaseRunner):
    """Test case H013: 缺失或伪造完整性凭证的拒绝."""

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
