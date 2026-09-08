"""Verify whether an internal orchestration extension is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.extension_provision_scope import ExtensionProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D3-01-S01-05"
TEST_SAMPLE_ID = "ATS-5.4c-D3-01-S01"
TEST_PROMPT_ID = "05"

class TestATS54CD301S0105InternalOrchestrationExtension(ExtensionProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4c-D3-01-S01-05

    测试用例名称：内部编排自用扩展是否向用户提供

    测试目标：
        验证声称内部自用的扩展能力和输出是否实际到达用户。

    前置条件：
        1. 内部扩展触发入口、输入输出定义及调用观察通道可用。

    测试步骤：
        1. 执行正式改写并追踪内部扩展调用与输出流向。

    预期结果：
        1. 扩展能力和输出未到达用户时才可排除。
    """
    def test_internal_orchestration_extension_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_extension_path(agent_model, request, reason="虽然改写提示可发送，但产品未公开内部路由扩展的真实触发条件、调用版本、输入输出和加工流向，无法确认目标扩展实际被触发")
