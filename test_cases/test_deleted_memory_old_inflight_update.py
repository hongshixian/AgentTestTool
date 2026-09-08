"""Verify an old in-flight update cannot revive deleted memory."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2c-D4-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.2c-D4-01-S01"
TEST_PROMPT_ID = "02"


class TestATS52CD401S0102DeletedMemoryOldInflightUpdate(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D4-01-S01-02

    测试用例名称：旧在途更新不得复活已确认删除的记忆

    测试目标：
        验证删除确认后释放旧更新不会复活记忆。

    前置条件：
        1. 测试记忆及其原文、向量和版本查询已就绪。
        2. 服务端记忆提交屏障和提交顺序证据可用。

    测试步骤：
        1. 在旧更新持久化前暂停其提交。
        2. 从另一会话删除记忆并确认后释放旧更新。

    预期结果：
        1. 旧更新被拒绝或冲突处置，已删记忆不再可用。
    """

    def test_deleted_memory_old_inflight_update(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能在产品记忆服务端接收后、持久化前设置提交屏障，也不能查询记录版本、删除完成顺序、原文库和向量索引；测试侧同步门不能控制产品内部提交。")
