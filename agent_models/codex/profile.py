"""Codex test model and executable, read only from explicit environment settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_TEST_MODEL = "gpt-6-luna"
DEFAULT_REASONING_EFFORT = "high"


@dataclass(frozen=True, slots=True)
class CodexTestProfile:
    """Settings for one Codex Model.

    The evaluator does not pin a release and does not manage credentials: Codex
    runs with the operator's already-authenticated ``CODEX_HOME``.
    """

    executable: str = "codex"
    model: str = DEFAULT_TEST_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT

    @classmethod
    def from_environment(cls) -> CodexTestProfile:
        return cls(
            executable=os.environ.get("CODEX_BIN", "").strip() or "codex",
            model=os.environ.get("CODEX_TEST_MODEL", "").strip() or DEFAULT_TEST_MODEL,
            reasoning_effort=os.environ.get("CODEX_TEST_REASONING_EFFORT", "").strip() or DEFAULT_REASONING_EFFORT,
        )
