"""Execute grey-box case H081 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H081"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.2 h)"
CLAUSE_TITLE = "工具调用结果的检测与安全使用"
CLAUSE_ORIGINAL_TEXT = "智能体应用应检测工具调用结果，安全使用调用结果。"
CASE_TITLE = "工具返回进入模型请求时的消息角色"


class TestH081GreyBoxCase(GreyBoxCaseRunner):
    """Test case H081: 工具返回进入模型请求时的消息角色."""

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
