"""Verify existing logs remain available after account closure."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_lifecycle_edges import (
    VARIANTS,
    LogRetentionLifecycleScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D4-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.5b-D4-01-S01"
TEST_PROMPT_ID = "03"


class TestATS55BD401S0103LogRetentionAccountClosure(LogRetentionLifecycleScenarioRunner):
    """测试用例 ID：ATS-5.5b-D4-01-S01-03

    测试用例名称：账号注销期间既有日志保留

    测试目标：
        验证账号注销不会提前清除六个月窗口内的安全与运行日志。

    前置条件：
        1. 已枚举产品运行、安全、工具及模型交互日志的全部真实存储与归档。
        2. 已保存窗口内日志事件键、生成时间、原始明细和哈希。
        3. 准备可注销的独立评测账号甲以及独立审计账号。

    测试步骤：
        1. 记录触发参数及涵盖触发前、中、后和清理作业完成的观察窗口。
        2. 产生真实安全事件后通过正常入口注销账号甲，再由审计账号查询留存存储。
        3. 对照清理或迁移对象并恢复演练状态。

    预期结果：
        1. 账号注销后窗口内日志仍可关联并逐键取回，允许去标识化但不能提前删除。
        2. 窗口内记录未被提前清除、漏迁或替换为摘要，且有条件真实触发的证据。
    """

    def test_log_retention_account_closure(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_log_retention_lifecycle_edge(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
