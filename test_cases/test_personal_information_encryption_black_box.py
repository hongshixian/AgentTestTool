"""Verify personal-information encryption behavior without source access."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.personal_information_encryption_inventory import PersonalInformationEncryptionInventoryScenarioRunner

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3a-D1-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.3a-D1-01-S01"
TEST_PROMPT_ID = "02"


class TestATS53AD101S0102PersonalInformationEncryptionBlackBox(PersonalInformationEncryptionInventoryScenarioRunner):
    """测试用例 ID：ATS-5.3a-D1-01-S01-02

    测试用例名称：无源码时的加密行为替代核验

    测试目标：
        通过真实流量替代核验各入口个人信息只经加密信道传输。

    前置条件：
        1. 专用账号和合成姓名电话已准备。
        2. 注册、资料、聊天和文件上传入口可用。
        3. 主链路、后台和第三方流量可解密观察。

    测试步骤：
        1. 注册登录并更新合成姓名电话。
        2. 在聊天和测试文件中再次提交相同内容。
        3. 核对各入口原始包、可读副本及保护层。

    预期结果：
        1. 个人信息只在有效加密信道内出现。
        2. 不存在明文或声明遗漏的未保护旁路。
    """

    def test_black_box_personal_information_encryption(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_encryption_inventory(agent_model, request, path="无源码加密替代实测")
