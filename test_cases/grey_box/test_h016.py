"""Execute grey-box case H016 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H016"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 e)"
CLAUSE_TITLE = "向第三方提供用户数据的同意与取消同意"
CLAUSE_ORIGINAL_TEXT = "智能体应用将用户数据提供给第三方前，应获取用户同意，并支持用户取消同意。"
CASE_TITLE = "第三方工具切换后的再次同意"


class TestH016GreyBoxCase(GreyBoxCaseRunner):
    """Test case H016: 第三方工具切换后的再次同意."""

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
