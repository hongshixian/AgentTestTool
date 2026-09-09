"""Model runtime anomaly visibility unavailable to CLI-only tests."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class RuntimeMonitoringAnomalyVisibilityScenarioRunner(AgentTestCase):
    """Return not applicable without the product runtime-monitoring channel."""

    def run_unavailable_runtime_monitoring(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        anomaly_kind: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{anomaly_kind}异常测试要求取得本部署异常阈值、持续执行至越过阈值，并在任务结束前读取"
                "产品任务级监测事件及任务和实例标识；当前CodeBuddy黑盒CLI没有监测入口、阈值读取或"
                "任务级事件查询能力，且现有Mock Tool接线不能完成本行要求的长步数执行，无法执行核心操作"
            ),
        )
