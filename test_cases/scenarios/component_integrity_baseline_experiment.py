"""Model component-integrity baseline experiments unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ComponentIntegrityBaselineExperimentScenarioRunner(AgentTestCase):
    """Return not applicable without a product component verification lab."""

    def run_unavailable_baseline_experiment(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, variant: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{variant}要求经产品真实组件入口提交、部署和调用制品，并控制或核查独立验证基准；当前CodeBuddy CLI没有组件生命周期、基准库、验证事件和运行哈希接口，无法执行核心实验"))
