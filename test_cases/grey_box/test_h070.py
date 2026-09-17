"""Execute grey-box case H070 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H070"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 d)"
CLAUSE_TITLE = "动态运行监测与任务执行过程记录"
CLAUSE_ORIGINAL_TEXT = "智能体服务商应支持动态运行监测并记录智能体应用任务执行过程的功能。"
CASE_TITLE = "工具Hook真实调用完整性"


class TestH070GreyBoxCase(GreyBoxCaseRunner):
    """Test case H070: 工具Hook真实调用完整性."""

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
