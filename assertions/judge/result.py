"""Structured Judge result."""

from dataclasses import dataclass
from enum import Enum


class JudgeStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class JudgeCriterion:
    criterion_id: str
    description: str
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    status: JudgeStatus
    reason: str
    matched_criteria: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status is JudgeStatus.PASS
