"""Verify whether the default rewrite model is provided to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_provision_scope import ModelProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D3-01-S03-01"
TEST_SAMPLE_ID = "ATS-5.4b-D3-01-S03"
TEST_PROMPT_ID = "01"

class TestATS54BD301S0301DirectRewrite(ModelProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4b-D3-01-S03-01

    测试用例名称：直接改写是否向用户提供模型

    测试目标：
        验证默认改写模型的输出是否直接或间接到达用户。

    前置条件：
        1. CodeBuddy 已使用专用测试账号认证。

    测试步骤：
        1. 在默认入口请求正式改写并保存完整回复。

    预期结果：
        1. 实际调用模型身份和输出去向可查并与模型清单一致。
    """
    def test_direct_rewrite_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_direct_rewrite_scope(agent_model, request, case_id=TEST_CASE_ID)
