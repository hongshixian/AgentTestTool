"""Four-state business result statistics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from assertions.outcome import AssessmentStatus

from .models import CaseResult


STATUS_ORDER = (
    AssessmentStatus.PASS,
    AssessmentStatus.FAIL,
    AssessmentStatus.NOT_APPLICABLE,
    AssessmentStatus.INCONCLUSIVE,
)


@dataclass(frozen=True, slots=True)
class OutcomeStatistic:
    """Count and percentage for one assessment outcome."""

    status: AssessmentStatus
    count: int
    percentage: float


def calculate_statistics(results: Iterable[CaseResult]) -> tuple[OutcomeStatistic, ...]:
    """Return all four outcomes in a stable presentation order."""
    items = tuple(results)
    total = len(items)
    return tuple(
        OutcomeStatistic(
            status=status,
            count=sum(item.status is status for item in items),
            percentage=(sum(item.status is status for item in items) / total * 100.0)
            if total
            else 0.0,
        )
        for status in STATUS_ORDER
    )
