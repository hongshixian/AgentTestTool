"""Verify bulk memory deletion remains consistent after network interruption."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2c-D4-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.2c-D4-01-S01"
TEST_PROMPT_ID = "01"


class TestATS52CD401S0101MemoryBulkDeleteNetworkInterruption(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D4-01-S01-01

    测试用例名称：批量删除断网

    测试目标：
        验证批量删除在客户端断网后保持确定且一致的状态。

    前置条件：
        1. 账号甲已写入并确认可召回二十条测试记忆。
        2. 记忆原文、向量、删除状态和补偿日志可查询。
        3. 客户端网络可控且删除进行状态可确认。

    测试步骤：
        1. 发起批量删除并在处理中中断客户端网络。
        2. 恢复连接后核查二十条记忆及补偿结果。

    预期结果：
        1. 最终状态一致且部分失败有明细和重试入口。
    """

    def test_memory_bulk_delete_network_interruption(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 没有产品长期记忆写入、批量删除和进行状态接口，也没有原文库、向量索引、删除状态或补偿日志 Provider；整体断开 CLI 网络不能确认在删除处理中触发。")
