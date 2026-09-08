"""Verify primary, replica, backup, and cross-region storage locations."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.storage_region_inventory import StorageRegionInventoryScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2f-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.2f-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS52FD101S0101PrimaryReplicaBackupRegionInventory(StorageRegionInventoryScenarioRunner):
    """测试用例 ID：ATS-5.2f-D1-01-S01-01

    测试用例名称：主从存储、备份及跨区域复制

    测试目标：
        核对各数据载体及复制目标的实际存储地域。

    前置条件：
        1. 服务商存储资源清单和云控制台可访问。
        2. 主从、备份、归档、索引、缓存和日志配置可查询。
        3. 出境适用材料已确定。

    测试步骤：
        1. 列出各数据项的全部存储载体。
        2. 从控制台核实各载体和复制目标的地域。
        3. 对照文档并列出疑似境外存储。

    预期结果：
        1. 数据与载体地域矩阵完整且证据一致。
        2. 境外复制目标均纳入有效适用范围。
    """

    def test_storage_regions_match_inventory(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_inventory(agent_model, request, scope="主从存储与复制地域")
