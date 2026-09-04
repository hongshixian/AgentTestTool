"""Structured Judge result."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    passed: bool
    reason: str

