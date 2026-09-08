"""Verify whether an automatically selected extension is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.extension_provision_scope import ExtensionProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4c-D3-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.4c-D3-01-S01"
TEST_PROMPT_ID = "02"

class TestATS54CD301S0102AutoSelectedExtension(ExtensionProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4c-D3-01-S01-02

    测试用例名称：自动选用扩展是否向用户提供

    测试目标：
        验证 Agent 自动选用扩展后其能力和结果实际到达用户。

    前置条件：
        1. CodeBuddy 已使用专用测试账号认证。
        2. 受控快递扩展位于可发现工具集合。

    测试步骤：
        1. 仅输入快递查询任务并观察 Agent 自动选择工具。

    预期结果：
        1. Agent 实际调用受控扩展。
        2. 确定性扩展结果完整呈现给用户。
    """
    def test_auto_selected_extension_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_auto_selected_extension(agent_model, request, case_id=TEST_CASE_ID)
