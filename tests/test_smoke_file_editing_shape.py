"""Verify deterministic behavior of the file-editing smoke case."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.result import AuthResult, AuthStatus, TurnResult
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.test_file_editing import TestATS00XD400S01FileEditing as FileEditingCase


class _Ledger:
    def record(self, source: str, kind: str, data: object) -> None:
        pass


@dataclass
class _AgentStub:
    workspace: Path
    replacement: str | None
    interaction_error: Exception | None = None
    capabilities: AgentCapabilities = AgentCapabilities(file_operations=True)
    environment: object = field(
        default_factory=lambda: SimpleNamespace(ledger=_Ledger())
    )

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED)

    def send_prompt(self, prompt: str, **_kwargs: object) -> TurnResult:
        if self.interaction_error is not None:
            raise self.interaction_error
        target_file = self.workspace / "agent_test_edit_target.txt"
        assert target_file.read_text(encoding="utf-8") == (
            "AgentTestTool file editing pending."
        )
        assert "AgentTestTool file editing passed." in prompt
        if self.replacement is not None:
            target_file.write_text(self.replacement, encoding="utf-8")
        return TurnResult(
            response="完成",
            raw_output="完成",
            stderr="",
            returncode=0,
            completed=True,
            duration_seconds=0.0,
            session_id="test-session",
        )


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


class TestSmokeFileEditingShape:
    def test_exact_replacement_passes(self, tmp_path: Path) -> None:
        agent = _AgentStub(
            workspace=tmp_path,
            replacement="AgentTestTool file editing passed.",
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            FileEditingCase().test_agent_edits_existing_file_with_requested_content(
                agent, _request()  # type: ignore[arg-type]
            )

        assert outcome.value.verdict.status is AssessmentStatus.PASS

    @pytest.mark.parametrize(
        "replacement",
        [None, "AgentTestTool file editing passed.\n", "wrong content"],
    )
    def test_missing_or_inexact_replacement_fails(
        self,
        tmp_path: Path,
        replacement: str | None,
    ) -> None:
        agent = _AgentStub(workspace=tmp_path, replacement=replacement)

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            FileEditingCase().test_agent_edits_existing_file_with_requested_content(
                agent, _request()  # type: ignore[arg-type]
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL

    def test_interaction_error_is_an_explicit_failure(self, tmp_path: Path) -> None:
        agent = _AgentStub(
            workspace=tmp_path,
            replacement=None,
            interaction_error=TimeoutError("simulated timeout"),
        )

        with pytest.raises(AssessmentOutcomeSignal, match="不通过.*交互失败") as outcome:
            FileEditingCase().test_agent_edits_existing_file_with_requested_content(
                agent, _request()  # type: ignore[arg-type]
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
