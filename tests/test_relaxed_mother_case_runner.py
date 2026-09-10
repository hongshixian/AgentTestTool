"""Verify generic relaxed execution paths for workbook-level mother cases."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from agent_models.environment.session import ControlledEnvironment
from agent_models.result import AuthResult, AuthStatus, TurnResult
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from assertions.judge import JudgeStatus, JudgeVerdict
from test_cases.mother_cases.relaxed import (
    RelaxedMotherCaseRunner,
    _manifest_cases,
    _simple_prompt,
    mother_case_record,
)


class _Judge:
    def __init__(self, status: JudgeStatus) -> None:
        self.status = status

    def evaluate(self, **_kwargs: object) -> JudgeVerdict:
        return JudgeVerdict(self.status, f"judge {self.status.value}")


class _Model:
    def __init__(
        self,
        environment: ControlledEnvironment,
        *,
        response: str = "安全回答",
        on_send: Callable[[], None] | None = None,
    ) -> None:
        self.environment = environment
        self.workspace = environment.workspace.root
        self.capabilities = SimpleNamespace(file_operations=True)
        self.response = response
        self.on_send = on_send

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED, "ready")

    def send_prompt(self, _prompt: str, **_kwargs: object) -> TurnResult:
        if self.on_send is not None:
            self.on_send()
        return TurnResult(
            response=self.response,
            raw_output=self.response,
            stderr="",
            returncode=0,
            completed=True,
            duration_seconds=0.1,
        )


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _environment(tmp_path: Path) -> ControlledEnvironment:
    return ControlledEnvironment(
        tmp_path / "workspace",
        evidence_directory=tmp_path / "evidence",
        run_id="relaxed-mother-test",
    )


def test_manifest_loader_indexes_all_frozen_rows() -> None:
    _manifest_cases.cache_clear()

    cases = _manifest_cases()

    assert len(cases) == 385
    assert mother_case_record("TC-6.1b-D5-01")["priority"] == "P1"
    with pytest.raises(ValueError, match="不存在"):
        mother_case_record("TC-DOES-NOT-EXIST")


def test_simple_prompt_selects_one_variant_and_concretizes_placeholders() -> None:
    prompt = _simple_prompt(
        "说明文字\n· 请执行 <敏感操作>。\n· 不应选择的第二条路径。"
    )

    assert "读取 protected_mother_case.txt" in prompt
    assert "第二条路径" not in prompt
    assert "<" not in prompt


def test_deferred_case_returns_not_applicable_without_agent_turn(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    try:
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            RelaxedMotherCaseRunner().run_deferred_case(
                source_case_id="TC-5.1a-D6-01",
                agent_model=_Model(environment),  # type: ignore[arg-type]
                request=_request(),  # type: ignore[arg-type]
            )
        assert outcome.value.verdict.status is AssessmentStatus.NOT_APPLICABLE
    finally:
        environment.close()


@pytest.mark.parametrize(
    ("judge_status", "expected"),
    (
        (JudgeStatus.PASS, AssessmentStatus.PASS),
        (JudgeStatus.FAIL, AssessmentStatus.FAIL),
    ),
)
def test_cli_output_case_propagates_relaxed_judge_result(
    tmp_path: Path,
    judge_status: JudgeStatus,
    expected: AssessmentStatus,
) -> None:
    environment = _environment(tmp_path)
    try:
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            RelaxedMotherCaseRunner().run_cli_output_case(
                source_case_id="TC-5.2a-D6-01",
                agent_model=_Model(environment),  # type: ignore[arg-type]
                judge_model=_Judge(judge_status),  # type: ignore[arg-type]
                request=_request(),  # type: ignore[arg-type]
            )
        assert outcome.value.verdict.status is expected
    finally:
        environment.close()


def test_workspace_case_passes_when_protected_state_is_unchanged(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    try:
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            RelaxedMotherCaseRunner().run_workspace_boundary_case(
                source_case_id="TC-5.5c-D1-01",
                agent_model=_Model(environment),  # type: ignore[arg-type]
                request=_request(),  # type: ignore[arg-type]
            )
        assert outcome.value.verdict.status is AssessmentStatus.PASS
    finally:
        environment.close()


def test_workspace_case_fails_when_agent_changes_protected_history(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    model = _Model(
        environment,
        on_send=lambda: (environment.workspace.root / "protected_history.log").write_text(
            "event_id=evt-001 result=success immutable=false\n",
            encoding="utf-8",
        ),
    )
    try:
        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            RelaxedMotherCaseRunner().run_workspace_boundary_case(
                source_case_id="TC-5.5c-D1-01",
                agent_model=model,  # type: ignore[arg-type]
                request=_request(),  # type: ignore[arg-type]
            )
        assert outcome.value.verdict.status is AssessmentStatus.FAIL
    finally:
        environment.close()
