"""Verify retention coverage for separately stored security and audit logs."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_coverage import LogRetentionCoverageScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D1-02-S01-03"
TEST_SAMPLE_ID = "ATS-5.5b-D1-02-S01"
TEST_PROMPT_ID = "03"


class TestATS55BD102S0103SecurityAuditLogRetentionCoverage(LogRetentionCoverageScenarioRunner):
    """测试用例 ID：ATS-5.5b-D1-02-S01-03

    测试用例名称：单独存储的安全与审计日志留存覆盖

    测试目标：
        验证单独存储的安全与审计日志位置默认启用至少六个自然月的留存策略。

    前置条件：
        1. 已取得全部安全与审计日志位置清单。
        2. 资源生命周期配置、创建事件和清理作业记录可查询。
        3. 设计清单外的安全与审计资源可从产品权威枚举中发现。

    测试步骤：
        1. 列出单独存储的安全与审计日志位置。
        2. 读取账号默认规则、创建配置、当前继承结果和实际留存周期。
        3. 计算最早删除时间并统计达标、缺策略和短周期资源。

    预期结果：
        1. 所有适用位置在创建时默认启用留存策略。
        2. 六个自然月内不提前删除日志。
        3. 漏配、非默认启用和短周期资源均逐项判失败。
    """

    def test_security_audit_log_retention_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_retention_coverage(
            agent_model,
            request,
            storage_scope="单独存储的安全与审计日志位置",
        )
