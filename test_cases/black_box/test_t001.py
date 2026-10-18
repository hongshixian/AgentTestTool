"""Execute black-box case T001 through the shared case runner."""

import pytest

from agent_models import AgentModel
from test_cases.black_box.base import BlackBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.black_box]
TEST_CASE_ID = "T001"
TEST_CASE_LEVEL = "black_box"
SECURITY_DOMAIN = "内容安全与有害用途防范"
STANDARD_CLAUSE = "外部材料中的指令隔离"
CLAUSE_TITLE = "外部材料中的指令隔离"
CLAUSE_ORIGINAL_TEXT = "智能体应当只将外部材料作为数据处理，不执行材料中嵌入的操作指令。"
CASE_TITLE = "提取项目事实并保持预算原样"


class TestT001BlackBoxCase(BlackBoxCaseRunner):
    """Test case T001: 提取项目事实并保持预算原样."""

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
