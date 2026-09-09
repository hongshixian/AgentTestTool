"""Model consistency-decision reconstruction unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ConsistencyDecisionReconstructionScenarioRunner(AgentTestCase):
    """Return not applicable without product decision logs and a plan hook."""

    def run_unavailable_decision_reconstruction(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, decision: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{decision}重建要求计划检查前收件人注入、一致性判定事件和产品运行/安全日志反查；当前CodeBuddy黑盒CLI无计划Hook或上述日志接口，无法完成核心操作"))
