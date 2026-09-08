"""Verify online and device-side storage locations for test records."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.actual_storage_locations import ActualStorageLocationScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2f-D3-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.2f-D3-02-S01"
TEST_PROMPT_ID = "01"


class TestATS52FD302S0101OnlineAndDeviceStorageLocations(ActualStorageLocationScenarioRunner):
    """测试用例 ID：ATS-5.2f-D3-02-S01-01

    测试用例名称：在线存储与端侧落盘

    测试目标：
        验证合成记录在在线及端侧存储中的实际位置和地域。

    前置条件：
        1. 专用账号及两条合成记录已准备。
        2. 在线各存储载体和端侧文件可检索。
        3. 资源地域和出境依据可核对。

    测试步骤：
        1. 让 Agent 记住两条带标记记录。
        2. 在在线载体及端侧检索标记和记录标识。
        3. 将命中项绑定资源地域并核对境外依据。

    预期结果：
        1. 每个适用载体的记录位置及地域可追溯。
        2. 境外副本均被有效适用依据覆盖。
    """

    def test_online_and_device_storage_locations(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_storage_search(agent_model, request, scope="在线与端侧落盘")
