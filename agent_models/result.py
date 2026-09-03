"""Normalized results returned by every Agent Model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuthResult:
    status: AuthStatus
    detail: str = ""

    @property
    def authenticated(self) -> bool:
        return self.status is AuthStatus.AUTHENTICATED


@dataclass(frozen=True, slots=True)
class TurnResult:
    response: str
    raw_output: str
    stderr: str
    returncode: int
    completed: bool
    duration_seconds: float
    session_id: str | None = None

