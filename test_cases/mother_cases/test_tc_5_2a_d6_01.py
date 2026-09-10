"""Run the relaxed CLI-output path for mother case TC-5.2a-D6-01."""

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.mother_cases.p1_output import P1OutputMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "TC-5.2a-D6-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-5.2a-D6-01"
REPRESENTATIVE_CHILD_ID = "ATS-5.2a-D6-01-S01-01"
REPRESENTATIVE_CHILD_SCRIPT = "test_cases/test_data_processing_trace_completeness.py"
PRIORITY = "P1"
CATEGORY = "J"


class TestTC52AD601DataProcessingTraceCompleteness(P1OutputMotherCaseRunner):
    """测试用例 ID：TC-5.2a-D6-01

    测试用例名称：数据处理行为的留痕完备性核查

    测试目标：
        通过一条完整 CLI 响应检查数据处理留痕描述是否出现明确失败事实。

    前置条件：
        1. 被测 Agent CLI 已安装并使用专用测试身份完成认证。
        2. Judge 配置可用于评价完整最终响应。

    测试步骤：
        1. 从 v3 母用例记录选择第一条具体测试输入。
        2. 通过真实 CLI 执行该输入并保存完整最终响应。
        3. 仅按母用例失败条件评价响应。

    预期结果：
        1. 明确命中失败事实时判定不通过。
        2. 未明确命中失败事实时按宽松口径判定通过。
    """

    def test_cli_output_path(
        self,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_p1_output_case(
            source_case_id=SOURCE_CASE_ID,
            agent_model=agent_model,
            judge_model=judge_model,
            request=request,
        )
