"""Verify concurrent memory clearing and repeated deletion are idempotent."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2c-D4-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.2c-D4-01-S01"
TEST_PROMPT_ID = "03"


class TestATS52CD401S0103MemoryDualClientClearIdempotentDelete(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D4-01-S01-03

    测试用例名称：双客户端清空和同条删除幂等

    测试目标：
        验证双客户端并发清空及重复删除保持幂等一致。

    前置条件：
        1. 同一账号的两个独立客户端和二十条测试记忆已就绪。
        2. 原文、向量、界面和任务日志可查询。

    测试步骤：
        1. 两端同时发起整体清空并确认请求重叠。
        2. 对同一已删记录再次发起删除。

    预期结果：
        1. 最终状态一致且重复删除不触发未处理异常。
    """

    def test_memory_dual_client_clear_idempotent_delete(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前模型工厂不能建立同一真实账号的两个独立产品客户端并操控记忆清空接口，也没有请求重叠确认、产品记忆原文/向量状态和任务日志观察能力。")
