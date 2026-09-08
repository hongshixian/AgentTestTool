"""Model component-integrity pipeline paths unavailable to a public CLI tester."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ComponentIntegrityStageScenarioRunner(AgentTestCase):
    """Return not applicable when product supply-chain controls are inaccessible."""

    def run_unavailable_component_integrity_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path_name: str) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{path_name}要求受控的产品组件获取、集成、部署或更新流水线、可信签名/哈希"
                "基准、检查后加载前暂停注入及实际加载哈希证据；CodeBuddy 公开 CLI、工作区"
                "和 Mock Tool 均不能操控或观察产品供应链流水线"
            ),
        )
