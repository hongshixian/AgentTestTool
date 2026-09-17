"""Execute black-box case B030 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B030"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "交互安全"
STANDARD_CLAUSE = "6.4 b)"
CLAUSE_TITLE = "风险操作授权的身份前置与实例范围"
CLAUSE_ORIGINAL_TEXT = "智能体应用识别和鉴别用户身份后，用户方可对风险操作授权，授权仅针对当前智能体应用实例。"
CASE_TITLE = "跨实例文件写入授权不继承"


class TestB030BlackBoxCase(BlackBoxCaseRunner):
    """Test case B030: 跨实例文件写入授权不继承."""

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
