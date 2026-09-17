"""Execute black-box case B010 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B010"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 b)"
CLAUSE_TITLE = "用户级数据访问隔离功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持用户级数据访问隔离功能。"
CASE_TITLE = "跨用户记忆任务文件不可见"


class TestB010BlackBoxCase(BlackBoxCaseRunner):
    """Test case B010: 跨用户记忆任务文件不可见."""

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
