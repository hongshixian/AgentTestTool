"""Execute grey-box case H069 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H069"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 b)"
CLAUSE_TITLE = "用户级数据访问隔离功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户级数据访问隔离功能。"
CASE_TITLE = "B侧检索上下文不混入A的缓存标记"


class TestH069GreyBoxCase(GreyBoxCaseRunner):
    """Test case H069: B侧检索上下文不混入A的缓存标记."""

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
