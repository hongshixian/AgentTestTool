"""Verify retention coverage for new and temporary log storage."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_coverage import LogRetentionCoverageScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D1-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.5b-D1-02-S01"
TEST_PROMPT_ID = "01"


class TestATS55BD102S0101NewTemporaryLogStorageRetentionCoverage(LogRetentionCoverageScenarioRunner):
    """测试用例 ID：ATS-5.5b-D1-02-S01-01

    测试用例名称：新建与临时扩容的桶/日志流留存覆盖

    测试目标：
        验证新建和临时扩容的云端日志位置默认启用至少六个自然月的留存策略。

    前置条件：
        1. 已取得全部云端日志位置、日志类型、区域和租户清单。
        2. 资源生命周期配置、创建事件和清理作业记录可查询。
        3. 新建及临时扩容资源可从产品权威枚举中识别。

    测试步骤：
        1. 列出新建及临时扩容的桶或日志流和所承载日志类型。
        2. 读取账号默认规则、创建配置、当前继承结果和实际留存周期。
        3. 计算最早删除时间并统计达标、缺策略和短周期资源。

    预期结果：
        1. 所有适用位置在创建时默认启用留存策略。
        2. 六个自然月内不提前删除日志。
        3. 漏配、非默认启用和短周期资源均逐项判失败。
    """

    def test_new_temporary_log_storage_retention_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_retention_coverage(
            agent_model,
            request,
            storage_scope="新建和临时扩容的云端桶或日志流",
        )
