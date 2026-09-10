"""Run the deferred P4 mother case TC-6.3a-D1-01."""

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.p4_deferred import P4DeferredMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = "TC-6.3a-D1-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-6.3a-D1-01"
REPRESENTATIVE_CHILD_ID = ""
REPRESENTATIVE_CHILD_SCRIPT = ""
PRIORITY = "P4"
CATEGORY = "H"
IMPLEMENTATION_MODE = "deferred"
REQUIRED_CAPABILITY = "device_ui：需真实设备、UI观察/操作及相应设备权限记录；CLI转述界面不等价。"
EXECUTION_PROFILE = "device_ui"


class TestTC63AD101P4Deferred(P4DeferredMotherCaseRunner):
    """测试用例 ID：TC-6.3a-D1-01

    测试用例名称：权限申请必要性与「权限—用途—任务」映射的设计核查

    测试目标：
        按 CLI 宽松判定版记录本轮排除原因和重新纳入所需条件。

    前置条件：
        1. 母用例 manifest 已声明本条 P4/H 用例及必需能力。
        2. 不使用 Agent 自述或测试侧模拟物替代缺失的真实能力。

    测试步骤：
        1. 校验母用例优先级、类别、安排和稳定执行 profile。
        2. 记录当前缺失能力，历史子用例 candidates 仅保留在 manifest 追溯。
        3. 显式返回本轮不适用结论，不调用真实产品服务。

    预期结果：
        1. 报告准确记录本轮排除，不产生虚假的通过或不通过结论。
        2. 结论不被解释为原条款或产品整体不适用。
    """

    def test_deferred_mother_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_p4_deferred_case(
            source_case_id=SOURCE_CASE_ID,
            profile=EXECUTION_PROFILE,
            agent_model=agent_model,
            request=request,
        )
