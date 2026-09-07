"""Product-neutral definitions for deterministic mock Agent tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent_models.evidence import JsonValue


@dataclass(frozen=True, slots=True)
class MockToolProfile:
    name: str
    content_type: str
    body: JsonValue


@dataclass(frozen=True, slots=True)
class ToolEffect:
    """Mutate a named in-memory value, never an external business resource."""

    operation: Literal["set", "append", "increment"]
    key: str
    value: JsonValue = None
    argument_path: tuple[str | int, ...] | None = None


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """A scripted response; error responses never apply their effects."""

    body: JsonValue
    content_type: str = "application/json"
    is_error: bool = False
    delay_seconds: float = 0
    gate: str | None = None
    effects: tuple[ToolEffect, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, JsonValue]
    responses: tuple[ToolResponse, ...]


@dataclass(frozen=True, slots=True)
class ToolSuite:
    definitions: tuple[ToolDefinition, ...]
    exhaustion: Literal["repeat_last", "error"] = "error"
