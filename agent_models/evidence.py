"""Product-neutral evidence types for security-oriented Agent tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from agent_models.result import TurnResult


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class EvidencePhase(str, Enum):
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Trusted identity context selected for one scenario run."""

    authorization: str = field(repr=False)
    user_id: str
    instance_id: str | None
    run_id: str

    def provider_payload(self) -> dict[str, JsonValue]:
        return {
            "authorization": self.authorization,
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
    context: RequestContext
    session_id: str | None = None

    def provider_payload(self) -> dict[str, JsonValue]:
        return {
            "sample_id": self.sample_id,
            "prompt_id": self.prompt_id,
            "repeat_index": self.repeat_index,
            "phase": self.phase.value,
            "request_context": self.context.provider_payload(),
            "session_id": self.session_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    phase: EvidencePhase
    data: JsonValue

    def judge_payload(self) -> dict[str, JsonValue]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.evidence_type,
            "phase": self.phase.value,
            "data": self.data,
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
            "raw_output": self.result.raw_output,
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
        return frozenset(built_in | {record.evidence_id for record in self.records})

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
