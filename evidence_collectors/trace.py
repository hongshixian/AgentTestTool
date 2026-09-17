"""Product-neutral immutable representation of an observed Agent trace."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias, cast


JsonScalar: TypeAlias = str | int | float | bool | None
JsonInput: TypeAlias = JsonScalar | Mapping[str, "JsonInput"] | Sequence["JsonInput"]
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
FrozenJson: TypeAlias = (
    JsonScalar | tuple["FrozenJson", ...] | Mapping[str, "FrozenJson"]
)


class TraceVisibility(str, Enum):
    """Whether an item is new for the turn or repeated supporting context."""

    CURRENT = "current"
    HISTORY = "history"
    BACKGROUND = "background"


class TracePhase(str, Enum):
    """Observation phase in which a trace item appeared."""

    REQUEST = "request"
    RESPONSE = "response"
    RUNTIME = "runtime"


class TraceReadyState(str, Enum):
    """How completely the collector observed and reconstructed an item."""

    READY = "ready"
    PARTIAL = "partial"
    REPLAYED = "replayed"
    UNAVAILABLE = "unavailable"


class ToolCallStage(str, Enum):
    """Observable stages in a tool call's lifecycle."""

    PROPOSED = "proposed"
    DISPATCHED = "dispatched"
    RECEIVED = "received"
    COMPLETED = "completed"
    RETURNED = "returned"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _validate_optional_text(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_text(value, field_name)


def _validate_common(
    *,
    sequence: int,
    observed_at: str | None,
    source: str,
    limitations: tuple[str, ...],
) -> None:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("sequence must be a non-negative integer")
    _validate_optional_text(observed_at, "observed_at")
    _require_text(source, "source")
    if any(not isinstance(item, str) or not item.strip() for item in limitations):
        raise ValueError("limitations must contain nonempty strings")


def _freeze_json(value: JsonInput, path: str = "payload") -> FrozenJson:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain non-finite numbers")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJson] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} object keys must be strings")
            frozen[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return tuple(
            _freeze_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise ValueError(f"{path} contains a non-JSON value: {type(value).__name__}")


def _json_payload(value: FrozenJson) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _json_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_payload(item) for item in value]
    return cast(JsonScalar, value)


def _common_payload(
    *,
    sequence: int,
    phase: TracePhase,
    visibility: TraceVisibility,
    ready_state: TraceReadyState,
    observed_at: str | None,
    source: str,
    limitations: tuple[str, ...],
) -> dict[str, JsonValue]:
    return {
        "sequence": sequence,
        "phase": phase.value,
        "visibility": visibility.value,
        "ready_state": ready_state.value,
        "observed_at": observed_at,
        "source": source,
        "limitations": list(limitations),
    }


@dataclass(frozen=True, slots=True)
class TraceMessage:
    """A message observed in a model request or response."""

    message_id: str
    role: str
    content: JsonInput
    sequence: int
    phase: TracePhase
    visibility: TraceVisibility = TraceVisibility.CURRENT
    ready_state: TraceReadyState = TraceReadyState.READY
    observed_at: str | None = None
    source: str = "network"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.message_id, "message_id")
        _require_text(self.role, "role")
        _validate_common(
            sequence=self.sequence,
            observed_at=self.observed_at,
            source=self.source,
            limitations=self.limitations,
        )
        object.__setattr__(self, "content", _freeze_json(self.content, "content"))

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "type": "message",
            "message_id": self.message_id,
            "role": self.role,
            "content": _json_payload(cast(FrozenJson, self.content)),
            **_common_payload(
                sequence=self.sequence,
                phase=self.phase,
                visibility=self.visibility,
                ready_state=self.ready_state,
                observed_at=self.observed_at,
                source=self.source,
                limitations=self.limitations,
            ),
        }


@dataclass(frozen=True, slots=True)
class TraceReasoning:
    """Reasoning data that a provider explicitly exposed to the evaluator."""

    reasoning_id: str
    content: JsonInput
    sequence: int
    phase: TracePhase = TracePhase.RESPONSE
    visibility: TraceVisibility = TraceVisibility.CURRENT
    ready_state: TraceReadyState = TraceReadyState.READY
    observed_at: str | None = None
    source: str = "network"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.reasoning_id, "reasoning_id")
        _validate_common(
            sequence=self.sequence,
            observed_at=self.observed_at,
            source=self.source,
            limitations=self.limitations,
        )
        object.__setattr__(self, "content", _freeze_json(self.content, "content"))

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "type": "reasoning",
            "reasoning_id": self.reasoning_id,
            "content": _json_payload(cast(FrozenJson, self.content)),
            **_common_payload(
                sequence=self.sequence,
                phase=self.phase,
                visibility=self.visibility,
                ready_state=self.ready_state,
                observed_at=self.observed_at,
                source=self.source,
                limitations=self.limitations,
            ),
        }


@dataclass(frozen=True, slots=True)
class TraceToolCall:
    """An observation of one stage in a tool call lifecycle."""

    tool_call_id: str
    name: str
    arguments: JsonInput
    stage: ToolCallStage
    sequence: int
    phase: TracePhase
    visibility: TraceVisibility = TraceVisibility.CURRENT
    ready_state: TraceReadyState = TraceReadyState.READY
    observed_at: str | None = None
    source: str = "network"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.tool_call_id, "tool_call_id")
        _require_text(self.name, "name")
        _validate_common(
            sequence=self.sequence,
            observed_at=self.observed_at,
            source=self.source,
            limitations=self.limitations,
        )
        object.__setattr__(
            self, "arguments", _freeze_json(self.arguments, "arguments")
        )

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "type": "tool_call",
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "arguments": _json_payload(cast(FrozenJson, self.arguments)),
            "stage": self.stage.value,
            **_common_payload(
                sequence=self.sequence,
                phase=self.phase,
                visibility=self.visibility,
                ready_state=self.ready_state,
                observed_at=self.observed_at,
                source=self.source,
                limitations=self.limitations,
            ),
        }


@dataclass(frozen=True, slots=True)
class TraceToolResult:
    """A tool result observed at completion or in a later model request."""

    tool_call_id: str
    content: JsonInput
    stage: ToolCallStage
    sequence: int
    phase: TracePhase
    is_error: bool = False
    visibility: TraceVisibility = TraceVisibility.CURRENT
    ready_state: TraceReadyState = TraceReadyState.READY
    observed_at: str | None = None
    source: str = "network"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.tool_call_id, "tool_call_id")
        if self.stage not in (ToolCallStage.COMPLETED, ToolCallStage.RETURNED):
            raise ValueError("tool result stage must be completed or returned")
        _validate_common(
            sequence=self.sequence,
            observed_at=self.observed_at,
            source=self.source,
            limitations=self.limitations,
        )
        object.__setattr__(self, "content", _freeze_json(self.content, "content"))

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "type": "tool_result",
            "tool_call_id": self.tool_call_id,
            "content": _json_payload(cast(FrozenJson, self.content)),
            "stage": self.stage.value,
            "is_error": self.is_error,
            **_common_payload(
                sequence=self.sequence,
                phase=self.phase,
                visibility=self.visibility,
                ready_state=self.ready_state,
                observed_at=self.observed_at,
                source=self.source,
                limitations=self.limitations,
            ),
        }


@dataclass(frozen=True, slots=True)
class TraceRuntimeEffect:
    """A process, file, network, or other runtime side effect."""

    effect_id: str
    effect_type: str
    action: str
    sequence: int
    details: JsonInput = field(default_factory=dict)
    target: str | None = None
    outcome: str | None = None
    tool_call_id: str | None = None
    phase: TracePhase = TracePhase.RUNTIME
    visibility: TraceVisibility = TraceVisibility.CURRENT
    ready_state: TraceReadyState = TraceReadyState.READY
    observed_at: str | None = None
    source: str = "runtime"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.effect_id, "effect_id")
        _require_text(self.effect_type, "effect_type")
        _require_text(self.action, "action")
        _validate_optional_text(self.target, "target")
        _validate_optional_text(self.outcome, "outcome")
        _validate_optional_text(self.tool_call_id, "tool_call_id")
        if self.phase is not TracePhase.RUNTIME:
            raise ValueError("runtime effects must use the runtime phase")
        _validate_common(
            sequence=self.sequence,
            observed_at=self.observed_at,
            source=self.source,
            limitations=self.limitations,
        )
        object.__setattr__(self, "details", _freeze_json(self.details, "details"))

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "type": "runtime_effect",
            "effect_id": self.effect_id,
            "effect_type": self.effect_type,
            "action": self.action,
            "details": _json_payload(cast(FrozenJson, self.details)),
            "target": self.target,
            "outcome": self.outcome,
            "tool_call_id": self.tool_call_id,
            **_common_payload(
                sequence=self.sequence,
                phase=self.phase,
                visibility=self.visibility,
                ready_state=self.ready_state,
                observed_at=self.observed_at,
                source=self.source,
                limitations=self.limitations,
            ),
        }


@dataclass(frozen=True, slots=True)
class ModelCall:
    """One model request/response exchange within an Agent turn."""

    model_call_id: str
    sequence: int
    request_id: str | None = None
    provider: str | None = None
    endpoint: str | None = None
    model: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    ready_state: TraceReadyState = TraceReadyState.READY
    messages: tuple[TraceMessage, ...] = ()
    visible_tools: tuple[JsonInput, ...] = ()
    reasoning: tuple[TraceReasoning, ...] = ()
    tool_calls: tuple[TraceToolCall, ...] = ()
    tool_results: tuple[TraceToolResult, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.model_call_id, "model_call_id")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ValueError("sequence must be a non-negative integer")
        if self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        for field_name in (
            "request_id",
            "provider",
            "endpoint",
            "model",
            "started_at",
            "completed_at",
        ):
            _validate_optional_text(getattr(self, field_name), field_name)
        if any(not isinstance(item, str) or not item.strip() for item in self.limitations):
            raise ValueError("limitations must contain nonempty strings")
        _require_unique_ids(self.messages, "message_id", "message")
        _require_unique_ids(self.reasoning, "reasoning_id", "reasoning")
        object.__setattr__(
            self,
            "visible_tools",
            tuple(_freeze_json(item, "visible_tools") for item in self.visible_tools),
        )

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "model_call_id": self.model_call_id,
            "sequence": self.sequence,
            "request_id": self.request_id,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "model": self.model,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "ready_state": self.ready_state.value,
            "messages": [item.to_payload() for item in self.messages],
            "visible_tools": [
                _json_payload(cast(FrozenJson, item)) for item in self.visible_tools
            ],
            "reasoning": [item.to_payload() for item in self.reasoning],
            "tool_calls": [item.to_payload() for item in self.tool_calls],
            "tool_results": [item.to_payload() for item in self.tool_results],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class AgentTurn:
    """All model calls and client-side effects caused by one user turn."""

    turn_id: str
    sequence: int
    user_input: JsonInput
    model_calls: tuple[ModelCall, ...] = ()
    runtime_effects: tuple[TraceRuntimeEffect, ...] = ()
    started_at: str | None = None
    completed_at: str | None = None
    ready_state: TraceReadyState = TraceReadyState.READY
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.turn_id, "turn_id")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ValueError("sequence must be a non-negative integer")
        if self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        _validate_optional_text(self.started_at, "started_at")
        _validate_optional_text(self.completed_at, "completed_at")
        if any(not isinstance(item, str) or not item.strip() for item in self.limitations):
            raise ValueError("limitations must contain nonempty strings")
        object.__setattr__(
            self, "user_input", _freeze_json(self.user_input, "user_input")
        )
        _require_unique_ids(self.model_calls, "model_call_id", "model call")
        _require_unique_ids(self.runtime_effects, "effect_id", "runtime effect")
        _validate_tool_lifecycle(self)

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "user_input": _json_payload(cast(FrozenJson, self.user_input)),
            "model_calls": [item.to_payload() for item in self.model_calls],
            "runtime_effects": [item.to_payload() for item in self.runtime_effects],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "ready_state": self.ready_state.value,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class AgentSession:
    """A single product session observed during an evaluator run."""

    session_id: str
    turns: tuple[AgentTurn, ...] = ()
    started_at: str | None = None
    ended_at: str | None = None
    ready_state: TraceReadyState = TraceReadyState.READY
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")
        _validate_optional_text(self.started_at, "started_at")
        _validate_optional_text(self.ended_at, "ended_at")
        if any(not isinstance(item, str) or not item.strip() for item in self.limitations):
            raise ValueError("limitations must contain nonempty strings")
        _require_unique_ids(self.turns, "turn_id", "turn")

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "session_id": self.session_id,
            "turns": [item.to_payload() for item in self.turns],
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "ready_state": self.ready_state.value,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class AgentTrace:
    """Versioned, run-scoped trace reconstructed from evaluator observations."""

    run_id: str
    product: str
    sessions: tuple[AgentSession, ...]
    schema_version: str = "1.0"
    test_case_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    ready_state: TraceReadyState = TraceReadyState.READY
    collector_health: str = "healthy"
    lost_event_count: int = 0
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        _require_text(self.product, "product")
        _require_text(self.schema_version, "schema_version")
        _validate_optional_text(self.test_case_id, "test_case_id")
        _validate_optional_text(self.started_at, "started_at")
        _validate_optional_text(self.ended_at, "ended_at")
        _require_text(self.collector_health, "collector_health")
        if (
            isinstance(self.lost_event_count, bool)
            or not isinstance(self.lost_event_count, int)
            or self.lost_event_count < 0
        ):
            raise ValueError("lost_event_count must be a non-negative integer")
        if any(not isinstance(item, str) or not item.strip() for item in self.limitations):
            raise ValueError("limitations must contain nonempty strings")
        _require_unique_ids(self.sessions, "session_id", "session")

    def to_payload(self) -> dict[str, JsonValue]:
        """Return a detached payload accepted by ``json.dumps``."""

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "test_case_id": self.test_case_id,
            "product": self.product,
            "sessions": [session.to_payload() for session in self.sessions],
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "ready_state": self.ready_state.value,
            "collector_health": self.collector_health,
            "lost_event_count": self.lost_event_count,
            "limitations": list(self.limitations),
        }


def _require_unique_ids(
    values: Sequence[object], attribute: str, description: str
) -> None:
    identifiers = [getattr(value, attribute) for value in values]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{description} identifiers must be unique")


def _validate_tool_lifecycle(turn: AgentTurn) -> None:
    stage_order = {stage: index for index, stage in enumerate(ToolCallStage)}
    observations: dict[str, list[tuple[int, ToolCallStage]]] = {}
    for model_call in turn.model_calls:
        for tool_call in model_call.tool_calls:
            observations.setdefault(tool_call.tool_call_id, []).append(
                (tool_call.sequence, tool_call.stage)
            )
        for tool_result in model_call.tool_results:
            observations.setdefault(tool_result.tool_call_id, []).append(
                (tool_result.sequence, tool_result.stage)
            )
    for tool_call_id, stages in observations.items():
        ordered = sorted(stages, key=lambda item: item[0])
        ranks = [stage_order[stage] for _, stage in ordered]
        if ranks != sorted(ranks):
            raise ValueError(
                f"tool call {tool_call_id!r} lifecycle stages must be ordered"
            )
