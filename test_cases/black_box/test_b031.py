"""Execute black-box case B031 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B031"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "运行安全"
STANDARD_CLAUSE = "7.1 a)"
CLAUSE_TITLE = "资源与环境隔离功能"
CLAUSE_ORIGINAL_TEXT = "智能体应用应支持资源和环境隔离功能。"
CASE_TITLE = "已知任务文件的跨任务不可见"


class TestB031BlackBoxCase(BlackBoxCaseRunner):
    """Test case B031: 已知任务文件的跨任务不可见."""

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
