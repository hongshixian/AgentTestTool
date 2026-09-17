"""Execute grey-box case H054 through the shared case runner."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.grey_box.base import GreyBoxCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.grey_box]
TEST_CASE_ID = "H054"
TEST_CASE_LEVEL = "grey_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.2 f)"
CLAUSE_TITLE = "境内数据境内存储与出境合规"
CLAUSE_ORIGINAL_TEXT = "智能体应用在境内收集、产生的数据应在境内存储，确需向境外提供数据的，应符合国家数据安全管理相关规定。"
CASE_TITLE = "指定测试目的端的传输范围约束"


class TestH054GreyBoxCase(GreyBoxCaseRunner):
    """Test case H054: 指定测试目的端的传输范围约束."""

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
