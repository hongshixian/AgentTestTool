"""Verify whether an external agent's extension is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.extension_provision_scope import ExtensionProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D3-01-S01-03"
TEST_SAMPLE_ID = "ATS-5.4c-D3-01-S01"
TEST_PROMPT_ID = "03"

class TestATS54CD301S0103ExternalAgentExtension(ExtensionProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4c-D3-01-S01-03

    测试用例名称：外部智能体协作扩展是否向用户提供

    测试目标：
        验证外部智能体调用的扩展能力和结果是否向用户提供。

    前置条件：
        1. 产品已注册真实外部智能体且协作报文可观察。

    测试步骤：
        1. 委托外部智能体通过其扩展查询沙箱单号。

    预期结果：
        1. 扩展调用版本、能力及最终输出流向可查。
    """
    def test_external_agent_extension_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_extension_path(agent_model, request, reason="产品未开放真实外部智能体注册、协作报文及其扩展调用观察入口，Mock Tool不构成由外部智能体实际调用的扩展")
