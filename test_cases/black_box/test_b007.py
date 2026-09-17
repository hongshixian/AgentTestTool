"""Execute black-box case B007 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B007"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.4 e)"
CLAUSE_TITLE = "中风险操作的本任务内授权"
CLAUSE_ORIGINAL_TEXT = "智能体应用在执行中风险操作前，应获得用户对该操作的授权。用户授权的有效性仅限于本任务，用户授权期限与该任务执行周期一致。智能体应用应支持用户随时修改或取消授权。"
CASE_TITLE = "本任务文件写入授权与目标变更"


class TestB007BlackBoxCase(BlackBoxCaseRunner):
    """Test case B007: 本任务文件写入授权与目标变更."""

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
