"""Verify storage regions remain domestic after disaster-recovery failover."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2f-D3-03-S01-02"
TEST_SAMPLE_ID = "ATS-5.2f-D3-03-S01"
TEST_PROMPT_ID = "02"


class TestATS52FD303S0102DisasterRecoveryStorageRegion(AgentTestCase):
    """测试用例 ID：ATS-5.2f-D3-03-S01-02

    测试用例名称：容灾切换后存储区域

    测试目标：
        验证容灾切换后境内账号的数据和副本仍在境内。

    前置条件：
        1. 产品具备获批的隔离容灾切换和恢复方案。
        2. 切换事件、备用区域和全部副本位置可查询。

    测试步骤：
        1. 切换前写入测试记忆并查询区域。
        2. 执行容灾切换后再次写入并查询区域。
        3. 恢复容灾配置。

    预期结果：
        1. 切换前后数据及副本均位于境内。
        2. 属地强制路由在切换后继续生效。
    """

    def test_disaster_recovery_storage_region(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架没有产品容灾切换控制、恢复能力或切换事件、备用区域、全部副本 region 和属地路由配置 Provider，不能执行真实容灾路径。")
