"""Shared runner for provider-side task storm containment paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class ProviderStormContainmentVariant:
    """One fine-grained provider-side containment path."""

    case_id: str
    case_name: str
    storm_kind: str
    containment_action: str


class ProviderStormContainmentScenarioRunner(AgentTestCase):
    """Model one provider-side storm containment path."""

    def run_provider_storm_containment(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: ProviderStormContainmentVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"当前框架不能在产品侧建立并持续观察{variant.storm_kind}，也没有服务商"
                f"{variant.containment_action}控制入口、产品资源曲线、在途任务终态和安全"
                "日志证据；测试侧线程停止或Mock Tool状态不能替代产品阻断与关停"
            ),
        )
