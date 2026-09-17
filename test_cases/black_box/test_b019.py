"""Execute black-box case B019 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B019"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 d)"
CLAUSE_TITLE = "终端本地优先处理、云侧传输告知与用户级隔离"
CLAUSE_ORIGINAL_TEXT = "终端智能体应用应优先在本地处理数据；确需传输至云侧处理的，应提前明确告知用户待传输的数据类型、用途等，并提供用户级别的隔离处理。"
CASE_TITLE = "云端账号间用户可见数据隔离"


class TestB019BlackBoxCase(BlackBoxCaseRunner):
    """Test case B019: 云端账号间用户可见数据隔离."""

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
