"""Shared execution of one representative path for a mother case."""

from __future__ import annotations

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.base import AgentTestCase
from test_cases.scenarios.mother_representative_paths import (
    RepresentativeRunner,
    resolve_representative_path,
)


class MotherCaseScenarioRunner(AgentTestCase):
    """Execute a retained representative scenario owned by the mother suite."""

    def run_representative_case(
        self,
        *,
        source_case_id: str,
        representative_child_id: str,
        representative_script: str,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        representative_runner = self._resolve_representative(
            representative_child_id,
            representative_script,
        )
        agent_model.environment.ledger.record(
            "pytest",
            "mother_case_representative_started",
            {
                "source_case_id": source_case_id,
                "representative_child_id": representative_child_id,
                "representative_script": representative_script,
            },
        )
        representative_runner(agent_model, judge_model, request, repeat_index)

    @staticmethod
    def _resolve_representative(
        representative_child_id: str,
        representative_script: str,
    ) -> RepresentativeRunner:
        return resolve_representative_path(
            representative_child_id,
            representative_script,
        )
