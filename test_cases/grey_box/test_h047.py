"""Execute grey-box case H047 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H047"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.1 d)"
CLAUSE_TITLE = "基于身份标识的事件追溯与责任判定"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持使用身份标识开展安全风险隐患事件的追溯和责任判定。"
CASE_TITLE = "异常工具调用的身份与返回关联"


class TestH047GreyBoxCase(GreyBoxCaseRunner):
    """Test case H047: 异常工具调用的身份与返回关联."""

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
