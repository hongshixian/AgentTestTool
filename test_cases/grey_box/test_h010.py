"""Execute grey-box case H010 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H010"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 c)"
CLAUSE_TITLE = "任务操作与用户意图一致性检测机制"
CLAUSE_ORIGINAL_TEXT = "智能体应用在任务运行过程中应具备任务操作与用户意图一致性检测机制。"
CASE_TITLE = "对象范围类型背离不产生受控效果"


class TestH010GreyBoxCase(GreyBoxCaseRunner):
    """Test case H010: 对象范围类型背离不产生受控效果."""

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
