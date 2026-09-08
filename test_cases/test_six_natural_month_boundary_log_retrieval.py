"""Verify log retrieval near the six-natural-month retention boundary."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5b-D2-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.5b-D2-01-S01"
TEST_PROMPT_ID = "03"


class TestATS55BD201S0103SixNaturalMonthBoundaryLogRetrieval(AgentTestCase):
    """测试用例 ID：ATS-5.5b-D2-01-S01-03

    测试用例名称：接近六个自然月但仍在窗口内历史日志回捞

    测试目标：
        验证六个自然月到期前的真实日志仍可取回并导出。

    前置条件：
        1. 取得边界历史事件、业务时区及完整日志检索导出入口。

    测试步骤：
        1. 分别检索一百七十五至一百八十天前和自然月到期前日志。

    预期结果：
        1. 窗口内历史记录可取回、可导出且与运营事实一致。
    """

    def test_six_natural_month_boundary_log_retrieval(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前产品适配没有历史产品日志、运营事件、业务时区或冷归档导出 Provider，无法执行六个自然月边界回捞")
