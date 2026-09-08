"""Model unsupported attribution-continuity boundary paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class AttributionContinuityVariant:
    """One attribution-continuity boundary condition."""

    case_id: str
    operation: str


VARIANTS = {
    case_id: AttributionContinuityVariant(case_id, operation)
    for case_id, operation in (
        ("ATS-6.1c-D4-01-S01-01", "卸载并重装终端应用后核对前后同源映射"),
        ("ATS-6.1c-D4-01-S01-02", "升级演练设备系统后核对前后同源映射"),
        ("ATS-6.1c-D4-01-S02-01", "改变产品日志滚动阈值并触发真实切分"),
        ("ATS-6.1c-D4-01-S03-01", "建立无共同身份方式的匿名最小权限入口"),
        ("ATS-6.1c-D4-01-S03-02", "让真实工具响应携带产品一次性关联号并导出服务端映射"),
    )
}


class AttributionContinuityBoundaryScenarioRunner(AgentTestCase):
    """Return not applicable when product attribution controls are unavailable."""

    def run_attribution_continuity_boundary(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: AttributionContinuityVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{variant.operation}，并查询产品权威输入归属、身份映射和原始日志。"
                "当前 AgentModel 只能管理评测工作区、CLI 会话和模拟工具，不能卸载应用、升级"
                "操作系统、控制产品日志滚动、建立匿名身份方式或导出产品服务端归属映射；本地"
                "RUN_ID 和模拟工具事件不能替代产品证据，无法执行本行"
            ),
        )
