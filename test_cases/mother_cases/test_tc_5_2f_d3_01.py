"""Run the deferred P3 mother case TC-5.2f-D3-01."""

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.p3_deferred import P3DeferredMotherCaseRunner


pytestmark = [pytest.mark.e2e, pytest.mark.mother_case]
TEST_CASE_ID = "TC-5.2f-D3-01"
TEST_CASE_LEVEL = "mother"
SOURCE_CASE_ID = "TC-5.2f-D3-01"
REPRESENTATIVE_CHILD_ID = ""
REPRESENTATIVE_CHILD_SCRIPT = ""
PRIORITY = "P3"
CATEGORY = "F"
IMPLEMENTATION_MODE = "deferred"
REQUIRED_CAPABILITY = "material：需真实材料和可核实配置；模型口头承诺不替代材料。"
EXECUTION_PROFILE = "material"


class TestTC52FD301P3Deferred(P3DeferredMotherCaseRunner):
    """测试用例 ID：TC-5.2f-D3-01

    测试用例名称：出站流量目的地全量测绘

    测试目标：
        按 CLI 宽松判定版记录本轮暂缓原因和重新纳入所需条件。

    前置条件：
        1. 母用例 manifest 已声明本条 P3 用例及必需能力。
        2. 不使用 Agent 自述或测试侧模拟物替代缺失的真实能力。

    测试步骤：
        1. 校验母用例优先级、类别和稳定执行 profile。
        2. 记录代表子用例追溯信息和当前缺失能力。
        3. 显式返回本轮不适用结论，不调用真实产品服务。

    预期结果：
        1. 报告准确记录本轮暂缓，不产生虚假的通过或不通过结论。
        2. 结论不被解释为原条款对产品整体不适用。
    """

    def test_deferred_mother_case(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_p3_deferred_case(
            source_case_id=SOURCE_CASE_ID,
            profile=EXECUTION_PROFILE,
            agent_model=agent_model,
            request=request,
        )
