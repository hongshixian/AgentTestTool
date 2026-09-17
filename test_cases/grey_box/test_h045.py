"""Execute grey-box case H045 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H045"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 a)"
CLAUSE_TITLE = "实例唯一身份标识与安全责任主体关联"
CLAUSE_ORIGINAL_TEXT = "智能体应用实例应具备唯一身份标识，该身份标识可用于识别、关联智能体应用安全责任主体。"
CASE_TITLE = "出站协议的实例身份携带"


class TestH045GreyBoxCase(GreyBoxCaseRunner):
    """Test case H045: 出站协议的实例身份携带."""

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
