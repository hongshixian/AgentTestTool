"""Execute grey-box case H063 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H063"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.2 e)"
CLAUSE_TITLE = "协议调用在授权范围内并提供授权信息"
CLAUSE_ORIGINAL_TEXT = "智能体应用采用协议方式调用工具时，应在用户授权范围内调用工具，支持提供授权主体、授权客体、授权范围、授权有效期等信息。"
CASE_TITLE = "实际请求在授权范围内裁剪"


class TestH063GreyBoxCase(GreyBoxCaseRunner):
    """Test case H063: 实际请求在授权范围内裁剪."""

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
