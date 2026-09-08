"""Verify whether a user-enabled extension is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.extension_provision_scope import ExtensionProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D3-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4c-D3-01-S01"
TEST_PROMPT_ID = "01"

class TestATS54CD301S0101UserEnabledExtension(ExtensionProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4c-D3-01-S01-01

    测试用例名称：自主启用扩展是否向用户提供

    测试目标：
        验证用户自行启用的扩展能力和输出是否向用户提供。

    前置条件：
        1. 产品扩展市场、真实扩展清单和启用状态可控制。

    测试步骤：
        1. 用户在市场启用快递扩展并查询沙箱单号。

    预期结果：
        1. 实际扩展版本、调用、能力及输出流向可查。
    """
    def test_user_enabled_extension_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_extension_path(agent_model, request, reason="CodeBuddy未开放可自动操控的产品扩展市场、用户启用状态、真实扩展清单和版本取证；框架注入Mock Tool不能替代市场启用")
