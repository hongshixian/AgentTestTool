"""Product-neutral request and result models for source-level white-box cases."""

from __future__ import annotations

from dataclasses import dataclass

from agent_models.evidence import EvidenceBundle, EvidenceStatus, JsonValue


@dataclass(frozen=True, slots=True)
class WhiteBoxCaseRequest:
    """Describe one bounded white-box harness execution."""

    case_id: str
    repeat_index: int
    timeout_seconds: float
    variants: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("white-box case_id must be nonempty")
        if type(self.repeat_index) is not int or self.repeat_index < 1:
            raise ValueError("white-box repeat_index must be a positive integer")
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise ValueError("white-box timeout_seconds must be positive")
        if not self.variants or any(not item.strip() for item in self.variants):
            raise ValueError("white-box variants must be nonempty names")
        if len(set(self.variants)) != len(self.variants):
            raise ValueError("white-box variants must be unique")


@dataclass(frozen=True, slots=True)
class WhiteBoxMetric:
    """One metric projected from available harness evidence."""

    name: str
    value: JsonValue
    status: EvidenceStatus
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("white-box metric name must be nonempty")
        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("white-box metric status must use EvidenceStatus")
        if not self.evidence_ids or any(not item.strip() for item in self.evidence_ids):
            raise ValueError("white-box metric evidence IDs must be nonempty")


@dataclass(frozen=True, slots=True)
class WhiteBoxCaseResult:
    """Structured output from a product-specific white-box harness."""

    case_id: str
    repeat_index: int
    execution_completed: bool
    cleanup_completed: bool
    metrics: tuple[WhiteBoxMetric, ...]
    evidence: EvidenceBundle
    missing_evidence: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip() or self.case_id != self.evidence.sample_id:
            raise ValueError("white-box result case ID must match its evidence bundle")
        if type(self.repeat_index) is not int or self.repeat_index < 1:
            raise ValueError("white-box result repeat_index must be positive")
        if type(self.execution_completed) is not bool or type(self.cleanup_completed) is not bool:
            raise ValueError("white-box completion flags must be booleans")
        names = tuple(item.name for item in self.metrics)
        if len(set(names)) != len(names):
            raise ValueError("white-box metric names must be unique")
        if any(not item.strip() for item in (*self.missing_evidence, *self.artifact_refs)):
            raise ValueError("white-box missing evidence and artifact references must be nonempty")

    def metric(self, name: str) -> WhiteBoxMetric | None:
        """Return a named metric without inventing a default value."""

        return next((item for item in self.metrics if item.name == name), None)


__all__ = ["WhiteBoxCaseRequest", "WhiteBoxCaseResult", "WhiteBoxMetric"]
