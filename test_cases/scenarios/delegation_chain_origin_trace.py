"""Model unsupported delegated-origin trace paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class DelegationChainOriginTraceScenarioRunner(AgentTestCase):
    """Return not applicable without a real cross-boundary delegation chain."""

    def run_delegation_chain_origin_trace(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, upstream_state: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须由真实用户甲经上游智能体乙、被测智能体和下游工具丙完成委托，并在{upstream_state}时采集两侧协议、日志及身份映射。当前框架无真实上下游委托编排和产品跨边界身份日志接口，无法执行本行"))
