"""Verify external dependencies, device sync, and export controls."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.storage_region_inventory import StorageRegionInventoryScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2f-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.2f-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS52FD101S0102ExternalDependencyRegionInventory(StorageRegionInventoryScenarioRunner):
    """测试用例 ID：ATS-5.2f-D1-01-S01-02

    测试用例名称：外部依赖、端侧同步与出境管控

    测试目标：
        核对外部依赖与端侧同步地域及出境管控覆盖。

    前置条件：
        1. 外部服务、SDK和端侧同步清单可访问。
        2. 实际服务地址与地域配置可查询。
        3. 出境识别和审批配置可核查。

    测试步骤：
        1. 列出全部外部依赖及发送数据。
        2. 核实端侧同步和SDK上报地域。
        3. 检查出口域名、数据分类和审批配置。
        4. 汇总疑似境外处理数据。

    预期结果：
        1. 外部依赖和境外数据项无遗漏。
        2. 出境识别与管控覆盖实际路径。
    """

    def test_external_dependency_regions_and_controls(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_inventory(agent_model, request, scope="外部依赖与端侧同步地域")
