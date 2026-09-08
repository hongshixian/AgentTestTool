"""Model unsupported concurrent product task-trace paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ConcurrentProductTaskTraceScenarioRunner(AgentTestCase):
    """Return not applicable without public task reconstruction access."""

    def run_concurrent_product_task_trace(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        operation: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{operation}。框架可编排有界并发和模拟工具同步，但 AgentModel 不提供产品"
                "真实任务 ID、运行/安全日志导出或任务链重建接口，且未提供真实子智能体委派观察；"
                "无法执行本行产品日志归集核查"
            ),
        )
