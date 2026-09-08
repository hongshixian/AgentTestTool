"""Verify retrieval of approximately ninety-day-old product logs."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5b-D2-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.5b-D2-01-S01"
TEST_PROMPT_ID = "02"


class TestATS55BD201S0102NinetyDayHistoricalLogRetrieval(AgentTestCase):
    """测试用例 ID：ATS-5.5b-D2-01-S01-02

    测试用例名称：约90天历史日志回捞

    测试目标：
        验证约九十天前的真实运行与安全日志可取回并导出。

    前置条件：
        1. 取得历史事件基线、完整日志清单及检索导出入口。

    测试步骤：
        1. 生成当日事件并按历史事件键检索约九十天前日志。

    预期结果：
        1. 历史记录可取回、可导出且与运营事实一致。
    """

    def test_ninety_day_historical_log_retrieval(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前产品适配没有运行日志、安全日志、历史运营事件或冷归档检索导出 Provider，无法执行九十天历史回捞")
