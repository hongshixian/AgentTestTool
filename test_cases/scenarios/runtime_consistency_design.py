"""Model runtime consistency-design paths unavailable to CLI tests."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RuntimeConsistencyDesignScenarioRunner(AgentTestCase):
    """Return not applicable without product consistency hooks."""

    def run_unavailable_consistency_path(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, path: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"{path}要求读取产品一致性检测设计或在计划生成后、实质操作检查前修改收件人，并取得判定事件；当前CodeBuddy黑盒CLI没有计划注入点、意图基准或一致性事件接口，无法执行核心核查"))
