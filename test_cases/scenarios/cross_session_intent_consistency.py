"""Shared runner for cross-session intent-consistency memory paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class CrossSessionIntentVariant:
    """One reviewed cross-session memory variant."""

    case_id: str
    case_name: str
    memory_disguise: str
    template_number: int
    interval: str
    session_scope: str


class CrossSessionIntentConsistencyScenarioRunner(AgentTestCase):
    """Model one cross-session intent-consistency path."""

    def run_cross_session_intent_consistency(
        self,
        agent_model: AgentModel,
        pytest_request: pytest.FixtureRequest,
        variant: CrossSessionIntentVariant,
    ) -> None:
        self.conclude_not_applicable(
            pytest_request,
            agent_model,
            reason=(
                "当前框架不能通过产品公开接口写入、确认、读取和清理真实长期记忆，也不能将新会话"
                f"绑定到本行要求的{variant.session_scope}并证明植入状态实际承接；因此无法建立"
                "记忆植入、利用和清理对照的因果闭环"
            ),
        )
