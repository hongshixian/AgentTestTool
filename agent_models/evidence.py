"""Product-neutral black-box evidence types for Agent tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from agent_models.result import TurnResult


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
MAX_JUDGE_RAW_OUTPUT_CHARS = 8_000


class EvidencePhase(str, Enum):
    BEFORE = "before"
    AFTER = "after"


class EvidenceStatus(str, Enum):
    """Collection status; only AVAILABLE records satisfy evidence requirements."""

    AVAILABLE = "available"
    MISSING = "missing"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNVERIFIED = "unverified"


class EvidenceAuthority(str, Enum):
    """Authority boundary of an evidence source, not a confidence score."""

    PRODUCT_PUBLIC_API = "product_public_api"
    PRODUCT_RUNTIME = "product_runtime"
    EVALUATOR_OBSERVED = "evaluator_observed"
    EVALUATOR_CONTROLLED = "evaluator_controlled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Describe the public channel that produced an evidence record."""

    provider: str
    channel: str
    authority: EvidenceAuthority
    product: str | None = None
    product_version: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.channel.strip():
            raise ValueError("evidence source provider and channel must be nonempty")

    def judge_payload(self) -> dict[str, JsonValue]:
        return {
            "provider": self.provider,
            "channel": self.channel,
            "authority": self.authority.value,
            "product": self.product,
            "product_version": self.product_version,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class EvidenceCorrelation:
    """Public identifiers that correlate evidence to the evaluator run."""

    run_id: str | None = None
    session_ids: tuple[str, ...] = ()
    request_ids: tuple[str, ...] = ()
    turn_ids: tuple[str, ...] = ()
    task_ids: tuple[str, ...] = ()
    tool_use_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            *self.session_ids,
            *self.request_ids,
            *self.turn_ids,
            *self.task_ids,
            *self.tool_use_ids,
        )
        if any(not value for value in values):
            raise ValueError("evidence correlation identifiers must be nonempty")

    def judge_payload(self) -> dict[str, JsonValue]:
        return {
            "run_id": self.run_id,
            "session_ids": list(self.session_ids),
            "request_ids": list(self.request_ids),
            "turn_ids": list(self.turn_ids),
            "task_ids": list(self.task_ids),
            "tool_use_ids": list(self.tool_use_ids),
        }


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Identity selectors exposed by a product's public CLI interface."""

    user_id: str
    instance_id: str | None
    run_id: str

    def provider_payload(self) -> dict[str, JsonValue]:
        return {
            "user_id": self.user_id,
            "instance_id": self.instance_id,
            "run_id": self.run_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    sample_id: str
    prompt_id: str
    repeat_index: int
    phase: EvidencePhase
    context: RequestContext | None = None
    session_id: str | None = None

    def provider_payload(self) -> dict[str, JsonValue]:
        return {
            "sample_id": self.sample_id,
            "prompt_id": self.prompt_id,
            "repeat_index": self.repeat_index,
            "phase": self.phase.value,
            "request_context": (
                self.context.provider_payload() if self.context is not None else None
            ),
            "session_id": self.session_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    phase: EvidencePhase
    data: JsonValue
    status: EvidenceStatus = EvidenceStatus.AVAILABLE
    source: EvidenceSource | None = None
    correlation: EvidenceCorrelation = field(default_factory=EvidenceCorrelation)
    proves: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.evidence_type.strip():
            raise ValueError("evidence id and type must be nonempty")
        if any(not item.strip() for item in (*self.proves, *self.limitations)):
            raise ValueError("evidence claims and limitations must be nonempty")

    @property
    def available(self) -> bool:
        return self.status is EvidenceStatus.AVAILABLE

    def judge_payload(self) -> dict[str, JsonValue]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.evidence_type,
            "phase": self.phase.value,
            "data": self.data,
            "status": self.status.value,
            "source": self.source.judge_payload() if self.source is not None else None,
            "correlation": self.correlation.judge_payload(),
            "proves": list(self.proves),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    prompt: str
    result: TurnResult

    def judge_payload(self) -> dict[str, JsonValue]:
        return {
            "prompt": self.prompt,
            "response": self.result.response,
            "completed": self.result.completed,
            "returncode": self.result.returncode,
            "stderr": self.result.stderr,
            "raw_output": self.result.raw_output[-MAX_JUDGE_RAW_OUTPUT_CHARS:],
            "duration_seconds": self.result.duration_seconds,
            "session_id": self.result.session_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    sample_id: str
    prompt_id: str
    run_id: str
    transcript: tuple[TranscriptTurn, ...]
    records: tuple[EvidenceRecord, ...]

    @property
    def available_evidence_ids(self) -> frozenset[str]:
        built_in = (
            {"conversation_transcript", "api_cli_runtime_result"}
            if self.transcript
            else set()
        )
        return frozenset(
            built_in
            | {record.evidence_id for record in self.records if record.available}
        )

    def missing_evidence(self, required_ids: set[str]) -> frozenset[str]:
        return frozenset(required_ids - self.available_evidence_ids)

    def judge_payload(self) -> dict[str, JsonValue]:
        turns = [turn.judge_payload() for turn in self.transcript]
        return {
            "sample_id": self.sample_id,
            "prompt_id": self.prompt_id,
            "run_id": self.run_id,
            "conversation_transcript": turns,
            "api_cli_runtime_result": turns,
            "external_evidence": [record.judge_payload() for record in self.records],
        }
