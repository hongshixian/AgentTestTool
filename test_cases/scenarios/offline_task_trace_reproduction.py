"""Model unsupported offline task trace reproduction paths."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase


class OfflineTaskTraceReproductionScenarioRunner(AgentTestCase):
    """Return not applicable without product trace export access."""

    def run_offline_task_trace_reproduction(self, agent_model: AgentModel, request: pytest.FixtureRequest, *, operation: str) -> None:
        self.conclude_not_applicable(request, agent_model, reason=(f"本行须{operation}并导出产品原始运行/安全日志、任务 ID 和后台重建件。当前 AgentModel 不提供这些公开接口，也不支持真实子智能体委派，无法执行离线重建步骤"))
