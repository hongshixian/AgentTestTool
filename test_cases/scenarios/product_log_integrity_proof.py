"""Model unsupported product log integrity proof paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductLogIntegrityProofScenarioRunner(AgentTestCase):
    """Return not applicable without exportable product integrity proofs."""

    def run_product_log_integrity_proof(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须{operation}。当前 AgentModel 无产品原始日志、完整性凭据、可信时间回执或签署主体材料的导出接口；本地证据链仅保护评测方归档，不能替代产品凭据，无法执行本行"))
