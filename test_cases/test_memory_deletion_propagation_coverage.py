"""Verify memory deletion propagates to every actual memory carrier and recall path."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e

TEST_CASE_ID = "ATS-5.2c-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.2c-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS52CD101S0102MemoryDeletionPropagationCoverage(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D1-01-S01-02

    测试用例名称：删除传播覆盖所有实际记忆载体

    测试目标：
        验证删除控制覆盖全部实际记忆副本，并阻止各召回路径继续使用已删内容。

    前置条件：
        1. 产品记忆载体清单、传播配置和召回过滤逻辑可只读审查。
        2. 账号已在全部实际载体建立可追踪测试记忆。

    测试步骤：
        1. 逐一核对各记忆载体的删除传播和时延。
        2. 检查关键词、向量和时间召回路径的删除过滤。
        3. 区分法定留痕与可再次使用的记忆副本。

    预期结果：
        1. 全部记忆副本均被删除或停止使用。
        2. 所有召回路径过滤已删内容，并有明确最长时延。
    """

    def test_memory_deletion_propagation_coverage(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="当前框架没有产品内部记忆载体清单、传播配置或召回过滤逻辑访问权，也不能查询向量索引、缓存、备份和画像副本。",
        )
