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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.criterion_id, str)
            or not self.criterion_id.strip()
            or not isinstance(self.description, str)
            or not self.description.strip()
        ):
            raise ValueError("Judge criterion id and description must be nonempty")
        if any(not isinstance(tag, str) or not tag.strip() for tag in self.tags):
            raise ValueError("Judge criterion tags must be nonempty")

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
