"""Lightweight immutable models for emitted ATIF-v1.7 trajectories."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from evidence_collectors.trace import JsonValue


ATIF_SCHEMA_VERSION = "ATIF-v1.7"
_SOURCES = frozenset({"system", "user", "agent"})


@dataclass(frozen=True, slots=True)
class AtifToolCall:
    tool_call_id: str
    function_name: str
    arguments: dict[str, JsonValue]
    extra: dict[str, JsonValue] = field(default_factory=dict)

    def to_payload(self) -> dict[str, JsonValue]:
        return copy.deepcopy(
            {
                "tool_call_id": self.tool_call_id,
                "function_name": self.function_name,
                "arguments": self.arguments,
                "extra": self.extra,
            }
        )


@dataclass(frozen=True, slots=True)
class AtifObservationResult:
    source_call_id: str
    content: str
    extra: dict[str, JsonValue] = field(default_factory=dict)

    def to_payload(self) -> dict[str, JsonValue]:
        return copy.deepcopy(
            {
                "source_call_id": self.source_call_id,
                "content": self.content,
                "extra": self.extra,
            }
        )


@dataclass(frozen=True, slots=True)
class AtifStep:
    step_id: int
    source: str
    message: str
    timestamp: str | None = None
    model_name: str | None = None
    reasoning_content: str | None = None
    tool_calls: tuple[AtifToolCall, ...] = ()
    observation_results: tuple[AtifObservationResult, ...] = ()
    is_copied_context: bool = False
    llm_call_count: int | None = None
    extra: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.step_id < 1:
            raise ValueError("ATIF step_id must start at 1")
        if self.source not in _SOURCES:
            raise ValueError(f"unsupported ATIF step source: {self.source}")

    def to_payload(self) -> dict[str, JsonValue]:
        observation: JsonValue = None
        if self.observation_results:
            observation = {
                "results": [item.to_payload() for item in self.observation_results]
            }
        return copy.deepcopy(
            {
                "step_id": self.step_id,
                "timestamp": self.timestamp,
                "source": self.source,
                "model_name": self.model_name,
                "reasoning_effort": None,
                "message": self.message,
                "reasoning_content": self.reasoning_content,
                "tool_calls": [item.to_payload() for item in self.tool_calls],
                "observation": observation,
                "metrics": None,
                "is_copied_context": self.is_copied_context,
                "llm_call_count": self.llm_call_count,
                "extra": self.extra,
            }
        )


@dataclass(frozen=True, slots=True)
class AtifTrajectory:
    session_id: str
    trajectory_id: str
    agent_name: str
    steps: tuple[AtifStep, ...]
    model_name: str | None = None
    notes: str | None = None
    extra: dict[str, JsonValue] = field(default_factory=dict)
    schema_version: str = ATIF_SCHEMA_VERSION

    def to_payload(self) -> dict[str, JsonValue]:
        """Return a detached ATIF document suitable for JSON serialization."""

        return copy.deepcopy(
            {
                "schema_version": self.schema_version,
                "session_id": self.session_id,
                "trajectory_id": self.trajectory_id,
                "agent": {
                    "name": self.agent_name,
                    "version": None,
                    "model_name": self.model_name,
                    "tool_definitions": [],
                    "extra": {},
                },
                "steps": [step.to_payload() for step in self.steps],
                "notes": self.notes,
                "final_metrics": {},
                "continued_trajectory_ref": None,
                "extra": self.extra,
                "subagent_trajectories": [],
            }
        )
