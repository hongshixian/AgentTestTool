"""Product-neutral definitions for deterministic mock Agent tools."""

from __future__ import annotations

from dataclasses import dataclass

from agent_models.evidence import JsonValue


@dataclass(frozen=True, slots=True)
class MockToolProfile:
    name: str
    content_type: str
    body: JsonValue
