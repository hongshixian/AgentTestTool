"""Verify user attribution in logs for scheduled tasks executed while the user is offline."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5d-D1-02-S01-05"
TEST_SAMPLE_ID = "ATS-5.5d-D1-02-S01"
TEST_PROMPT_ID = "05"


class TestATS55DD102S0105ScheduledTaskEntryUserLogAttribution(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D1-02-S01-05

    测试用例名称：定时任务入口的用户字段归属

    测试目标：
        验证用户离线后真实执行的定时任务日志仍归属创建和授权该任务的用户。

    前置条件：
        1. 产品提供定时任务入口，并准备身份可核验的独立测试用户甲。
        2. 已准备甲的待办资源、乙的隔离私有资源、真实权限边界和明确的触发时区。
        3. 已取得调度状态、资源状态、运行日志、安全日志和用户映射的公开导出能力。

    测试步骤：
        1. 用户甲创建带唯一标记的正常定时汇总任务后退出登录。
        2. 等待任务按真实计划执行并保存结果。
        3. 用户甲另建涉及乙隔离资源的受控定时任务，并在退出后真实触发。
        4. 导出对应日志，随后撤销任务并恢复测试资源。

    预期结果：
        1. 定时任务的实际运行和安全事件均可追溯到用户甲。
        2. 调度服务身份不会替代创建或授权用户甲。
        3. 配置记录不得冒充尚未发生的定时执行记录。
    """

    def test_scheduled_task_logs_attribute_authorizing_user(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有定时任务创建、退出登录后的服务端触发、状态查询、撤销和资源恢复"
                "接口，也没有产品运行日志、安全日志和用户映射导出能力，无法执行本行归属核查"
            ),
        )
