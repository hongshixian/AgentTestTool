"""Execute grey-box case H026 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H026"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 a)"
CLAUSE_TITLE = "资源与环境隔离功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持资源和环境隔离功能。"
CASE_TITLE = "已声明调用次数上限的外部生效"


class TestH026GreyBoxCase(GreyBoxCaseRunner):
    """Test case H026: 已声明调用次数上限的外部生效."""

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
