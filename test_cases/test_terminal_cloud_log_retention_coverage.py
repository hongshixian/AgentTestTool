"""Verify retention coverage for terminal and cloud-uploaded logs."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.log_retention_coverage import LogRetentionCoverageScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.5b-D1-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.5b-D1-02-S01"
TEST_PROMPT_ID = "04"


class TestATS55BD102S0104TerminalCloudLogRetentionCoverage(LogRetentionCoverageScenarioRunner):
    """测试用例 ID：ATS-5.5b-D1-02-S01-04

    测试用例名称：终端本地及上报云端日志留存覆盖

    测试目标：
        验证终端上报云端的日志位置默认启用至少六个自然月的留存策略，并记录本地留存事实。

    前置条件：
        1. 已取得终端本地日志及其云端上报位置清单。
        2. 云端资源生命周期配置、创建事件和清理作业记录可查询。
        3. 本地日志和实际云端上报日志可明确区分。

    测试步骤：
        1. 列出终端本地日志和实际上报云端的位置及日志类型。
        2. 读取云端默认规则、创建配置、当前继承结果和实际留存周期。
        3. 计算云端最早删除时间并记录本地留存事实。

    预期结果：
        1. 所有上报云端的位置在创建时默认启用留存策略。
        2. 云端日志六个自然月内不提前删除。
        3. 本地留存事实只作记录，不替代云端判定。
    """

    def test_terminal_cloud_log_retention_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_retention_coverage(
            agent_model,
            request,
            storage_scope="终端本地日志和实际上报云端的日志位置",
        )
