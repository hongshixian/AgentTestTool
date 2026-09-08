"""Verify the real trigger of a declared fallback model."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.model_provision_scope import ModelProvisionScopeScenarioRunner

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.4b-D3-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.4b-D3-01-S01"
TEST_PROMPT_ID = "02"

class TestATS54BD301S0102DeclaredFallbackTrigger(ModelProvisionScopeScenarioRunner):
    """测试用例 ID：ATS-5.4b-D3-01-S01-02

    测试用例名称：声明降级模型的真实触发

    测试目标：
        验证真实降级模型及其输出是否属于向用户提供范围。

    前置条件：
        1. 主模型故障注入、路由配置和真实模型身份可取证。

    测试步骤：
        1. 完成主模型摘要基线。
        2. 使主模型超时并重复请求。

    预期结果：
        1. 降级模型身份和输出去向可查并与清单一致。
    """
    def test_declared_fallback_trigger(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_unavailable_scope_path(agent_model, request, reason="产品未开放主模型故障注入、真实路由配置、最终模型身份和模型清单，无法触发并确认声明的降级模型")
