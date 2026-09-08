"""Model storage-region inventory reviews unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class StorageRegionInventoryScenarioRunner(AgentTestCase):
    """Return not applicable without provider resource inventories."""

    def run_unavailable_inventory(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, scope: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{scope}要求云控制台、实际资源region、复制目标和外部依赖配置清单；这些是服务商内部配置，当前第三方CodeBuddy CLI与受控工作区均不可读取，无法执行核心核查"))
