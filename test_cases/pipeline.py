"""Normalized per-case execution events shared by every assessment suite."""

from __future__ import annotations

import time
from contextlib import contextmanager
from enum import StrEnum
from typing import Iterator

import pytest

from agent_models import AgentModel
from assertions.outcome import AssessmentOutcomeSignal, AssessmentStatus, AssessmentVerdict


PIPELINE_SOURCE = "test_case_pipeline"
PIPELINE_SCHEMA_VERSION = "1.0"
_ACTIVE_DEPTH = "_agent_test_pipeline_active_depth"
_CONCLUSION_RECORDED = "_agent_test_pipeline_conclusion_recorded"


class PipelinePhase(StrEnum):
    INITIALIZE = "initialize"
    CAPABILITY_CHECK = "capability_check"
    ENVIRONMENT_SETUP = "environment_setup"
    EVIDENCE_COLLECTION = "evidence_collection"
    EXERCISE = "exercise"
    EVIDENCE_PROJECTION = "evidence_projection"
    ASSERTION = "assertion"
    CLEANUP = "cleanup"
    CONCLUSION = "conclusion"


def case_identity(request: pytest.FixtureRequest) -> tuple[str, str]:
    module = getattr(request.node, "module", None)
    nodeid = str(getattr(request.node, "nodeid", "unknown-case") or "unknown-case")
    case_id = str(getattr(module, "TEST_CASE_ID", nodeid) or nodeid)
    case_level = str(getattr(module, "TEST_CASE_LEVEL", "unknown") or "unknown").strip().lower()
    return case_id, case_level


def pipeline_phase_active(request: pytest.FixtureRequest) -> bool:
    return bool(getattr(request.node, _ACTIVE_DEPTH, 0))


def _record(
    agent_model: AgentModel,
    kind: str,
    data: dict[str, object],
    correlation_id: str,
) -> None:
    ledger = agent_model.environment.ledger
    try:
        ledger.record(PIPELINE_SOURCE, kind, data, correlation_id)
    except TypeError:
        # Lightweight unit-test ledgers written before correlation IDs accept 3 args.
        ledger.record(PIPELINE_SOURCE, kind, data)


def _data(
    request: pytest.FixtureRequest,
    phase: PipelinePhase,
    *,
    repeat_index: int,
    duration_seconds: float | None = None,
    status: str | None = None,
    reason: str | None = None,
    evidence_ids: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
) -> dict[str, object]:
    case_id, case_level = case_identity(request)
    payload: dict[str, object] = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "case_id": case_id,
        "case_level": case_level,
        "repeat_index": repeat_index,
        "phase": phase.value,
        "evidence_ids": list(evidence_ids),
        "artifact_refs": list(artifact_refs),
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = round(duration_seconds, 6)
    if status is not None:
        payload["status"] = status
    if reason:
        payload["reason"] = reason
    return payload


def record_case_event(
    request: pytest.FixtureRequest,
    agent_model: AgentModel,
    kind: str,
    *,
    status: str | None = None,
    reason: str | None = None,
) -> None:
    case_id, case_level = case_identity(request)
    _record(
        agent_model,
        kind,
        {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "case_id": case_id,
            "case_level": case_level,
            "status": status,
            "reason": reason,
        },
        case_id,
    )


@contextmanager
def pipeline_phase(
    request: pytest.FixtureRequest,
    agent_model: AgentModel,
    phase: PipelinePhase,
    *,
    repeat_index: int = 1,
    evidence_ids: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
) -> Iterator[None]:
    case_id, _ = case_identity(request)
    correlation_id = f"{case_id}:repeat-{repeat_index}:{phase.value}"
    started = time.monotonic()
    _record(
        agent_model, "phase_started",
        _data(request, phase, repeat_index=repeat_index), correlation_id,
    )
    setattr(request.node, _ACTIVE_DEPTH, getattr(request.node, _ACTIVE_DEPTH, 0) + 1)
    try:
        yield
    except AssessmentOutcomeSignal as signal:
        verdict = signal.verdict
        kind = (
            "phase_not_applicable"
            if verdict.status is AssessmentStatus.NOT_APPLICABLE
            else "phase_completed"
        )
        _record(
            agent_model, kind,
            _data(
                request,
                phase,
                repeat_index=repeat_index,
                duration_seconds=time.monotonic() - started,
                status=verdict.status.value,
                reason=verdict.reason,
            ),
            correlation_id,
        )
        if not getattr(request.node, _CONCLUSION_RECORDED, False):
            record_conclusion(request, agent_model, verdict)
        raise
    except BaseException as error:
        _record(
            agent_model, "phase_failed",
            _data(
                request,
                phase,
                repeat_index=repeat_index,
                duration_seconds=time.monotonic() - started,
                status=AssessmentStatus.FAIL.value,
                reason=f"{type(error).__name__}: {error}",
            ),
            correlation_id,
        )
        raise
    else:
        _record(
            agent_model, "phase_completed",
            _data(
                request,
                phase,
                repeat_index=repeat_index,
                duration_seconds=time.monotonic() - started,
                evidence_ids=evidence_ids,
                artifact_refs=artifact_refs,
            ),
            correlation_id,
        )
    finally:
        depth = max(0, int(getattr(request.node, _ACTIVE_DEPTH, 1)) - 1)
        setattr(request.node, _ACTIVE_DEPTH, depth)


def record_conclusion(
    request: pytest.FixtureRequest,
    agent_model: AgentModel,
    verdict: AssessmentVerdict,
) -> None:
    if getattr(request.node, _CONCLUSION_RECORDED, False):
        return
    setattr(request.node, _CONCLUSION_RECORDED, True)
    case_id, _ = case_identity(request)
    correlation_id = f"{case_id}:conclusion"
    _record(
        agent_model, "phase_started",
        _data(request, PipelinePhase.CONCLUSION, repeat_index=1), correlation_id,
    )
    _record(
        agent_model, "phase_completed",
        _data(
            request,
            PipelinePhase.CONCLUSION,
            repeat_index=1,
            duration_seconds=0.0,
            status=verdict.status.value,
            reason=verdict.reason,
        ),
        correlation_id,
    )
    record_case_event(
        request,
        agent_model,
        "case_completed",
        status=verdict.status.value,
        reason=verdict.reason,
    )


__all__ = [
    "PIPELINE_SCHEMA_VERSION",
    "PIPELINE_SOURCE",
    "PipelinePhase",
    "case_identity",
    "pipeline_phase",
    "pipeline_phase_active",
    "record_case_event",
    "record_conclusion",
]
