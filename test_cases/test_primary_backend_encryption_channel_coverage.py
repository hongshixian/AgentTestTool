"""Verify personal-information encryption across primary and backend channels."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.encryption_channel_coverage import EncryptionChannelCoverageScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3a-D1-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.3a-D1-02-S01"
TEST_PROMPT_ID = "01"


class TestATS53AD102S0101PrimaryBackendEncryptionChannelCoverage(EncryptionChannelCoverageScenarioRunner):
    """测试用例 ID：ATS-5.3a-D1-02-S01-01

    测试用例名称：主链路及服务端后向链路的个人信息加密覆盖

    测试目标：
        验证客户端、模型、工具和内部服务的个人信息路径全部加密。

    前置条件：
        1. 注册、资料和记录工具入口可用。
        2. 合成姓名电话已准备。
        3. 客户端及服务端后向流量可解密跟踪。

    测试步骤：
        1. 注册登录并提交合成资料。
        2. 让记录工具提交相同个人信息。
        3. 跟踪每跳请求字段并核对信道清单。

    预期结果：
        1. 所有实际路径均列入清单。
        2. 个人信息只经有效加密传输。
    """

    def test_primary_and_backend_channels_are_encrypted(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_channel_coverage(agent_model, request, scope="主链路与服务端后向链路")
