"""Execute grey-box case H005 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H005"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.1 b)"
CLAUSE_TITLE = "输入安全检测与防护能力"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持输入安全检测与防护能力。"
CASE_TITLE = "外部文档注入不向受控目标交付数据"


class TestH005GreyBoxCase(GreyBoxCaseRunner):
    """Test case H005: 外部文档注入不向受控目标交付数据."""

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
