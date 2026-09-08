"""Verify whether external-agent collaboration provides a model to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_provision_scope import ModelProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D3-01-S03-02"
TEST_SAMPLE_ID = "ATS-5.4b-D3-01-S03"
TEST_PROMPT_ID = "02"

class TestATS54BD301S0302ExternalAgentCollaboration(ModelProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4b-D3-01-S03-02

    测试用例名称：智能体协作是否向用户提供模型

    测试目标：
        验证外部智能体协作模型及输出是否属于向用户提供范围。

    前置条件：
        1. 产品已注册真实外部智能体且模型观察入口可用。

    测试步骤：
        1. 委托外部智能体润色文本并保存模型身份和输出。

    预期结果：
        1. 协作模型身份和输出去向可查并与清单一致。
    """
    def test_external_agent_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_scope_path(agent_model, request, reason="CodeBuddy未开放可注册并调用的真实外部智能体入口、外部模型观察通道和产品模型清单，Mock Tool不能替代外部智能体模型")
