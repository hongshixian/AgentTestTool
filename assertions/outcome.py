"""Define assessment outcomes that are independent from pytest execution outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


ASSESSMENT_STATUS_PROPERTY = "assessment_status"
ASSESSMENT_REASON_PROPERTY = "assessment_reason"
ASSESSMENT_MISSING_EVIDENCE_PROPERTY = "assessment_missing_evidence"


class AssessmentStatus(str, Enum):
    """Statuses defined by the authoritative assessment workbook."""

    PASS = "通过"
    FAIL = "不通过"
    NOT_APPLICABLE = "不适用"
    INCONCLUSIVE = "无法判定"


@dataclass(frozen=True, slots=True)
class AssessmentVerdict:
    """A product assessment result kept separate from pytest's run status."""

    status: AssessmentStatus
    reason: str
    missing_evidence: tuple[str, ...] = ()


class AssessmentOutcomeSignal(Exception):
    """Internal control signal emitted only by an explicit case assertion."""

    def __init__(self, verdict: AssessmentVerdict) -> None:
        self.verdict = verdict
        super().__init__(f"{verdict.status.value}：{verdict.reason}")


def mock_inconclusive_assertion(
    *,
    reason: str,
    missing_evidence: tuple[str, ...],
    execution_completed: bool,
) -> AssessmentVerdict:
    """Return an inconclusive result only after the target function ran successfully."""
    if execution_completed is not True:
        raise ValueError("无法判定只能在目标功能成功执行后产生")
    normalized_reason = reason.strip()
    normalized_evidence = tuple(item.strip() for item in missing_evidence if item.strip())
    if not normalized_reason:
        raise ValueError("无法判定必须说明原因")
    if not normalized_evidence:
        raise ValueError("无法判定必须列出缺失证据")
    return AssessmentVerdict(
        status=AssessmentStatus.INCONCLUSIVE,
        reason=normalized_reason,
        missing_evidence=normalized_evidence,
    )


def assessment_verdict(
    status: AssessmentStatus,
    *,
    reason: str,
) -> AssessmentVerdict:
    """Build a terminal four-state verdict from an explicit case assertion."""
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError(f"{status.value}必须说明原因")
    return AssessmentVerdict(status=status, reason=normalized_reason)
