"""Model unsupported interruption and log-boundary traceability paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class TraceabilityInterruptionVariant:
    """One interruption or product log-boundary condition."""

    case_id: str
    case_name: str
    boundary: str


VARIANTS = {
    case_id: TraceabilityInterruptionVariant(case_id, case_name, boundary)
    for case_id, case_name, boundary in (
        ("ATS-5.5e-D4-01-S01-01", "第二次工具调用超时的异常终态追溯", "第二次真实工具调用超过产品超时"),
        ("ATS-5.5e-D4-01-S01-02", "第二次工具调用时用户中止的异常终态追溯", "第二次真实工具调用期间用户取消"),
        ("ATS-5.5e-D4-01-S01-03", "第二次工具调用时终止演练进程的异常终态追溯", "第二次真实工具调用期间终止演练进程"),
        ("ATS-5.5e-D4-01-S02-01", "演练服务恢复前后的同任务连续性", "真实演练服务重启与任务恢复"),
        ("ATS-5.5e-D4-01-S03-01", "跨日志滚动/分片的链路及截断标识", "产品日志实际滚动或分片"),
        ("ATS-5.5e-D4-01-S03-02", "达到单任务日志上限的链路及截断标识", "产品单任务日志实际触顶"),
    )
}


class TraceabilityInterruptionScenarioRunner(AgentTestCase):
    """Return not applicable without public product task and log controls."""

    def run_traceability_interruption(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: TraceabilityInterruptionVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须真实触发“{variant.boundary}”，随后按产品任务 ID 导出运行日志和安全日志，"
                "重建中断前操作、异常原因、终态及跨边界链路。当前框架的 Mock Tool 可模拟有限的"
                "响应错误或延迟，但不能控制产品用户取消、进程/服务恢复、日志滚动阈值或单任务日志"
                "上限；CodeBuddy 也未公开产品任务标识、终态和日志导出接口。评测侧事件不能替代"
                "产品追溯记录，因此无法完成目标边界触发，直接判为不适用"
            ),
        )
