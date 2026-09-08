"""Shared runner for non-protocol data cleanup coverage paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class NonProtocolCleanupVariant:
    """One non-protocol acquisition channel and data-destination pair."""

    case_id: str
    case_name: str
    acquisition_channel: str
    data_class: str
    destination: str


class NonProtocolDataCleanupScenarioRunner(AgentTestCase):
    """Model one non-protocol data cleanup coverage path."""

    def run_non_protocol_data_cleanup(
        self,
        agent_model: AgentModel,
        pytest_request: pytest.FixtureRequest,
        variant: NonProtocolCleanupVariant,
    ) -> None:
        self.conclude_not_applicable(
            pytest_request,
            agent_model,
            reason=(
                f"当前 CodeBuddy STDIO 适配没有端侧“{variant.acquisition_channel}”采集入口，"
                f"也不能定位或只读检索产品真实“{variant.destination}”及派生副本；"
                "受控工作区与 Mock Tool 不等价于产品非协议采集通道和数据落点，无法执行本行"
            ),
        )
