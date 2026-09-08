"""Verify backup, replica, and overseas analysis storage locations."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.actual_storage_locations import ActualStorageLocationScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2f-D3-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.2f-D3-02-S01"
TEST_PROMPT_ID = "02"


class TestATS52FD302S0102BackupReplicaAnalysisStorageLocations(ActualStorageLocationScenarioRunner):
    """测试用例 ID：ATS-5.2f-D3-02-S01-02

    测试用例名称：备份、复制与境外分析副本

    测试目标：
        验证合成记录在备份、复制及分析存储中的实际位置和地域。

    前置条件：
        1. 专用账号及两条合成记录已准备。
        2. 备份、归档、复制、分析和训练存储可检索。
        3. 资源地域和出境依据可核对。

    测试步骤：
        1. 让 Agent 记住两条带标记记录。
        2. 等待包含本次写入的异步备份完成。
        3. 在备份、复制及分析载体检索记录并核对地域。

    预期结果：
        1. 每个适用载体的记录位置及地域可追溯。
        2. 境外副本均被有效适用依据覆盖。
    """

    def test_backup_replica_and_analysis_locations(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_storage_search(agent_model, request, scope="备份复制与分析副本")
