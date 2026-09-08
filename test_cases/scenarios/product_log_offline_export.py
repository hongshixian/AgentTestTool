"""Model unsupported product log offline export paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductLogOfflineExportScenarioRunner(AgentTestCase):
    """Return not applicable without product log export access."""

    def run_product_log_offline_export(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, log_type: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须从产品实际入口导出{log_type}原始 JSON/CSV、字段字典及分页范围，并在离线环境复核。当前 AgentModel 不提供产品日志查询导出接口；本地 EvidenceLedger 不是被测产品日志，无法执行本行"))
