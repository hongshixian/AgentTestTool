"""Model unsupported product task-trace reconstruction paths."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class ProductTaskTraceReconstructionScenarioRunner(AgentTestCase):
    """Return not applicable without a public product trace reconstruction API."""

    def run_product_task_trace_reconstruction(
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
                f"本行须{operation}。当前 AgentModel 可观察评测方模拟工具事件，但不提供被测产品的"
                "真实任务 ID、运行/安全日志检索导出或任务链重建入口，且无公开父子任务关联观察能力；"
                "无法完成必要的产品日志重建步骤"
            ),
        )
