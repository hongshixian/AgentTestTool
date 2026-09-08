"""Verify deleted memory is not injected into new recommendation tasks during the cleanup wait."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-5.2c-D4-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.2c-D4-02-S01"
TEST_PROMPT_ID = "02"


class TestATS52CD402S0102DeletedMemoryNotInjectedDuringWait(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D4-02-S01-02

    测试用例名称：删除等待期不再注入新推荐任务

    测试目标：
        验证从删除开始，等待物理清理期间也不会把已删记忆注入新任务。

    前置条件：
        1. 账号长期记忆已保存并可召回指定测试标记。
        2. 产品删除入口、清理等待期和实际模型上下文可查询。

    测试步骤：
        1. 自助删除测试记忆并记录时间。
        2. 立即及等待期内在新会话请求个性化推荐。
        3. 采集实际模型上下文和缓存来源。

    预期结果：
        1. 已删记忆从删除开始不再注入新任务。
        2. 推荐内容须结合上下文来源判定，不以文本巧合作结论。
    """

    def test_deleted_memory_not_injected_during_wait(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架不能通过产品公开接口创建和删除真实长期记忆，也不能读取实际模型上下文、记忆注入来源或服务端缓存。",
        )
