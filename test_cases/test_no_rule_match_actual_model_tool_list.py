"""Verify the actual model tool list when no task rule is matched."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-6.2a-D1-01-S01-03"
TEST_SAMPLE_ID = "ATS-6.2a-D1-01-S01"
TEST_PROMPT_ID = "03"


class TestATS62AD101S0103NoRuleMatchActualModelToolList(AgentTestCase):
    """测试用例 ID：ATS-6.2a-D1-01-S01-03

    测试用例名称：无任何任务规则命中时实际模型工具清单

    测试目标：
        验证无任务规则命中时默认不向模型提供业务工具。

    前置条件：
        1. 产品开放必要性规则状态控制和实际模型工具清单。

    测试步骤：
        1. 配置无规则命中并执行天气查询后比较各工具清单。

    预期结果：
        1. 无规则命中时不提供业务工具。
    """

    def test_no_rule_match_actual_model_tool_list(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能控制产品必要性规则为无命中状态，也不能观察实际发送给模型的工具清单，无法触发本路径")
