"""Execute black-box case B039 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B039"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.1 d)"
CLAUSE_TITLE = "待输出结果的安全检测与防护"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持对待输出结果的安全检测与防护功能。"
CASE_TITLE = "分片及编码输出的可恢复标记检查：10片重组"


class TestB039BlackBoxCase(BlackBoxCaseRunner):
    """Test case B039: 分片及编码输出的可恢复标记检查：10片重组."""

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
