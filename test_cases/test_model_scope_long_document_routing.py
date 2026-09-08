"""Verify whether long-document routing provides a model to users."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_provision_scope import ModelProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D3-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.4b-D3-01-S01"
TEST_PROMPT_ID = "01"

class TestATS54BD301S0101LongDocumentRouting(ModelProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4b-D3-01-S01-01

    测试用例名称：长文档路由是否向用户提供模型

    测试目标：
        验证长文档实际路由模型及其输出是否属于向用户提供范围。

    前置条件：
        1. 产品上下文上限、路由配置、真实模型调用及清单可读取。

    测试步骤：
        1. 上传超过实际上下文上限的会议文档并请求全文摘要。

    预期结果：
        1. 实际模型身份和输出去向可查并与清单一致。
    """
    def test_long_document_routing_scope(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_scope_path(agent_model, request, reason="产品未公开实际上下文上限、路由控制、真实模型调用身份和模型清单，无法构造并验证超限长文档路由")
