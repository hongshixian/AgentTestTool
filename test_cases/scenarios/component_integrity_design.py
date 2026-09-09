"""Model component-integrity design checks unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ComponentIntegrityDesignScenarioRunner(AgentTestCase):
    """Return not applicable without product component lifecycle controls."""

    def run_unavailable_component_integrity(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求产品组件提交、集成、部署、加载及验证日志和可信基准；当前CodeBuddy CLI适配器没有组件管理入口、运行模块哈希或完整性事件接口，无法执行核心核查"))
