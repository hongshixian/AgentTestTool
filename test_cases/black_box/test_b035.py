"""Execute black-box case B035 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B035"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.1 d)"
CLAUSE_TITLE = "待输出结果的安全检测与防护"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持对待输出结果的安全检测与防护功能。"
CASE_TITLE = "正文附件与流式输出不含敏感原值：下载附件"


class TestB035BlackBoxCase(BlackBoxCaseRunner):
    """Test case B035: 正文附件与流式输出不含敏感原值：下载附件."""

    def test_black_box_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_black_box_case(
            case_id=TEST_CASE_ID,
            agent_model=agent_model,
            request=request,
        )
