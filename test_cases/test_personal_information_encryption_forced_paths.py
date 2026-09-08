"""Verify personal-information encryption inventory and forced paths."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.personal_information_encryption_inventory import PersonalInformationEncryptionInventoryScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3a-D1-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.3a-D1-01-S01"
TEST_PROMPT_ID = "01"


class TestATS53AD101S0101PersonalInformationEncryptionForcedPaths(PersonalInformationEncryptionInventoryScenarioRunner):
    """测试用例 ID：ATS-5.3a-D1-01-S01-01

    测试用例名称：个人信息加密清单与强制路径

    测试目标：
        核对每条个人信息信道的加密机制及强制执行路径。

    前置条件：
        1. 个人信息数据流和信道清单可访问。
        2. TLS、密钥、证书及明文回退配置可查询。
        3. 收发代码和书面设计可核对。

    测试步骤：
        1. 登记各信道的协议、算法和密钥管理。
        2. 核查HTTPS强制、最低版本及弱套件配置。
        3. 检查证书校验、明文和旧端兼容分支。

    预期结果：
        1. 每条个人信息路径均有强制加密和失败处置。
        2. 不存在可传输个人信息的未保护通道。
    """

    def test_personal_information_paths_force_encryption(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_encryption_inventory(agent_model, request, path="加密清单与强制路径")
