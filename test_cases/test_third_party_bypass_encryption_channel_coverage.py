"""Verify personal-information encryption across third-party and bypass channels."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.encryption_channel_coverage import EncryptionChannelCoverageScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3a-D1-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.3a-D1-02-S01"
TEST_PROMPT_ID = "02"


class TestATS53AD102S0102ThirdPartyBypassEncryptionChannelCoverage(EncryptionChannelCoverageScenarioRunner):
    """测试用例 ID：ATS-5.3a-D1-02-S01-02

    测试用例名称：第三方组件与旁路的个人信息加密覆盖

    测试目标：
        验证统计、广告、崩溃、推送等旁路中的个人信息传输均加密。

    前置条件：
        1. 带第三方组件的测试客户端已就绪。
        2. 合成姓名电话及测试通知已准备。
        3. 客户端和服务端各类出站流量可捕获。

    测试步骤：
        1. 填入合成资料并冷启动正常页面。
        2. 触发测试崩溃、推送及事件通知。
        3. 检查各旁路字段和加密状态。

    预期结果：
        1. 实际旁路均有字段及加密记录。
        2. 承载个人信息的旁路全部加密。
    """

    def test_third_party_and_bypass_channels_are_encrypted(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_channel_coverage(agent_model, request, scope="第三方组件与旁路")
