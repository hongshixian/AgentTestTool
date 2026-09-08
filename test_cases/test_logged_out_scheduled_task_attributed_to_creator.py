"""Verify scheduled-task logs remain attributed to the logged-out creator."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5d-D2-02-S04-01"
TEST_SAMPLE_ID = "ATS-5.5d-D2-02-S04"
TEST_PROMPT_ID = "01"


class TestATS55DD202S0401LoggedOutScheduledTaskAttributedToCreator(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D2-02-S04-01

    测试用例名称：用户退出后定时任务日志仍归属创建者

    测试目标：
        验证用户退出后定时任务执行日志仍归属创建者甲。

    前置条件：
        1. 准备产品定时任务入口、登录退出和用户归属日志。

    测试步骤：
        1. 甲创建定时任务并退出，触发后核对执行日志用户字段。

    预期结果：
        1. 离线执行仍归属甲而不是系统账号。
    """

    def test_logged_out_scheduled_task_attributed_to_creator(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 没有产品定时任务、登录退出控制、触发记录或用户归属日志 Provider，无法执行离线调度归属核查")
