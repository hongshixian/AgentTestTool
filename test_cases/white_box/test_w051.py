"""Record deferred white-box case W051 without executing product steps."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase
from test_cases.pipeline import PipelinePhase, pipeline_phase


pytestmark = [pytest.mark.e2e, pytest.mark.white_box]
TEST_CASE_ID = "W051"
TEST_CASE_LEVEL = "white_box"
SECURITY_DOMAIN = "基础安全"
STANDARD_CLAUSE = "5.4 c)"
CLAUSE_TITLE = "扩展（技能、插件）的预先安全评估"
CLAUSE_ORIGINAL_TEXT = "智能体服务商向用户提供的扩展（如技能、插件等）应预先通过安全评估。"
CASE_TITLE = "扩展评估结果约束发布分支"
DEFERRED_REASON = "缺少与被测部署版本匹配的源码、可复现测试构建、真实生产入口、可替换内部依赖、代码调用 Spy 及控制分支清单，无法执行白盒分支核验"


class TestW051DeferredWhiteBoxCase(AgentTestCase):
    """测试用例 ID：W051

    测试用例名称：扩展评估结果约束发布分支

    测试目标：
        记录当前缺少厂商源码与白盒测试构建能力的测试要求。

    前置条件：
        1. 当前第三方测评框架不具备本题所需的白盒能力。

    测试步骤：
        1. 不执行产品测试步骤。

    预期结果：
        1. 直接记录为不适用，并说明当前暂未实现的原因。
    """

    def test_case_not_implemented(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        with pipeline_phase(request, agent_model, PipelinePhase.CAPABILITY_CHECK):
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=f"当前暂未实现：{DEFERRED_REASON}",
            )
