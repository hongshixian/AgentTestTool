"""Verify an ordinary user can discover memory deletion controls and understand their scope."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-5.2c-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.2c-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS52CD101S0101MemoryDeletionEntryDiscoverability(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D1-01-S01-01

    测试用例名称：普通用户发现删除入口及确认范围

    测试目标：
        验证普通用户可自行发现记忆删除入口，并确认删除粒度、范围和不可恢复性。

    前置条件：
        1. 普通账号已通过正常对话建立三条测试记忆。
        2. 产品首页、会话记忆和长期记忆界面可操作。

    测试步骤：
        1. 由未看过说明的用户从首页寻找删除入口。
        2. 在对话中询问删除方法并核对实际入口。
        3. 检查删除粒度、确认文案和各记忆载体入口。

    预期结果：
        1. 用户可在规定点击次数内找到删除入口。
        2. 至少支持单条和清空，并清楚说明范围。
    """

    def test_memory_deletion_entry_discoverability(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前 STDIO CLI 框架不能操控或计数产品首页点击，也不能可靠建立并枚举短期记忆、长期记忆和画像标签的删除入口。",
        )
