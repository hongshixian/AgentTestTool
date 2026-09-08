"""Model unsupported product log retention fidelity paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductLogRetentionFidelityScenarioRunner(AgentTestCase):
    """Return not applicable without product retention storage access."""

    def run_product_log_retention_fidelity(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须{operation}并读取被测产品留存存储。当前 AgentModel 无产品日志检索、冷热归档、生命周期策略或历史原始明细接口；评测方本地证据不代表产品留存，无法执行本行"))
