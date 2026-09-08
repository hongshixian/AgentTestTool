"""Model degraded-state termination paths unavailable to the current CLI adapter."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


class TaskTerminationDegradedStateScenarioRunner(AgentTestCase):
    """Return not applicable when the product termination lifecycle is inaccessible."""

    def run_unavailable_termination_path(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        degraded_state: str,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"{degraded_state}场景必须用产品原生任务标识和终止入口控制真实长任务，"
                "并独立操控客户端网络或终端应用状态；当前 CodeBuddy CLI 适配器不提供"
                "任务级终止确认、客户端断网、应用退后台息屏或进程重启后任务状态查询能力，"
                "无法完成核心操作"
            ),
        )
