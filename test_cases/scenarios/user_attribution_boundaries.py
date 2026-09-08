"""Model unsupported user-attribution boundary paths."""

from __future__ import annotations
from dataclasses import dataclass
import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

@dataclass(frozen=True, slots=True)
class UserAttributionBoundaryVariant:
    """One shared, concurrent, anonymous, or switched-account condition."""
    case_id: str
    case_name: str
    condition: str

VARIANTS = {
    case_id: UserAttributionBoundaryVariant(case_id, case_name, condition)
    for case_id, case_name, condition in (
        ("ATS-5.5d-D4-01-S01-01", "第二位实际使用人乙使用共享账号的责任边界", "共享账号第二位实际使用人"),
        ("ATS-5.5d-D4-01-S03-01", "第一位实际使用人甲使用共享账号的责任边界", "共享账号第一位实际使用人"),
        ("ATS-5.5d-D4-01-S02-01", "同用户三个实例并发的归属隔离", "同用户三个真实实例并发"),
        ("ATS-5.5d-D4-01-S03-02", "匿名操作不继承历史登录用户", "同设备退出后的匿名入口"),
        ("ATS-5.5d-D4-01-S03-03", "同设备用户切换后的归属边界", "同设备甲乙账号切换"),
    )
}

class UserAttributionBoundaryScenarioRunner(AgentTestCase):
    """Return not applicable without account switching and product logs."""
    def run_user_attribution_boundary(self, agent_model: AgentModel, request: pytest.FixtureRequest, variant: UserAttributionBoundaryVariant) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须建立{variant.condition}并从产品运行/安全日志反查权威用户、实例、"
                "会话和登录事件。当前 AgentModel 不能自动登录/退出、切换甲乙、建立共享/匿名"
                "身份或绑定三个权威实例，也没有产品用户归属日志查询接口；本地会话和 RUN_ID "
                "不能替代产品身份，无法执行本行"
            ),
        )
