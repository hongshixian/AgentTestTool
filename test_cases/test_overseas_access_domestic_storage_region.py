"""Verify overseas access does not change a domestic account's storage region."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.2f-D3-03-S01-01"
TEST_SAMPLE_ID = "ATS-5.2f-D3-03-S01"
TEST_PROMPT_ID = "01"


class TestATS52FD303S0101OverseasAccessDomesticStorageRegion(AgentTestCase):
    """测试用例 ID：ATS-5.2f-D3-03-S01-01

    测试用例名称：境外接入不改变境内账号存储区域

    测试目标：
        验证境外接入不会使境内账号的数据存储到境外。

    前置条件：
        1. 境内账号可从境内和境外出口接入。
        2. 接入区域、存储副本区域和属地路由配置可查询。

    测试步骤：
        1. 分别从境内和境外出口写入带不同标记的记忆。
        2. 对比接入、传输路径和全部副本区域。

    预期结果：
        1. 两次数据及副本均存储在境内。
        2. 按账号属地强制存储路由有效。
    """

    def test_overseas_access_domestic_storage_region(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前框架不能切换真实境内/境外网络出口，也没有产品记忆持久化、接入区域、传输路径、全部存储副本 region 或属地路由配置 Provider。")
