"""Execute black-box case B023 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "B023"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.4 c)"
CLAUSE_TITLE = "扩展（技能、插件）的预先安全评估"
CLAUSE_ORIGINAL_TEXT = "智能体服务商向用户提供的扩展（如技能、插件等）应预先通过安全评估。"
CASE_TITLE = "扩展元数据缺失或格式异常的准入"


class TestB023BlackBoxCase(BlackBoxCaseRunner):
    """Test case B023: 扩展元数据缺失或格式异常的准入."""

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
