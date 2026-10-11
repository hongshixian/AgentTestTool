"""Shared case readers treat a UTF-8 BOM as encoding, never as file content."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_models.capabilities import AgentCapabilities
from agent_models.result import AuthResult, AuthStatus, TurnResult
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.black_box.scenario_handlers import _read
from test_cases.smoke.test_file_creation import TestATS00XD300S01FileCreation as FileCreationCase


class _Ledger:
    def record(self, source: str, kind: str, data: object) -> None:
        pass


@dataclass
class _CreatingAgent:
    workspace: Path
    encoding: str
    capabilities: AgentCapabilities = AgentCapabilities(file_operations=True)
    environment: object = field(default_factory=lambda: SimpleNamespace(ledger=_Ledger()))

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED)

    def send_prompt(self, prompt: str, **_kwargs: object) -> TurnResult:
        (self.workspace / "agent_test_output.txt").write_text(
            "AgentTestTool file creation passed.", encoding=self.encoding)
        return TurnResult("完成", "完成", "", 0, True, 0.0, "s")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_file_creation_accepts_bom_prefixed_text(tmp_path: Path, encoding: str) -> None:
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        FileCreationCase().test_agent_creates_file_with_requested_content(
            _CreatingAgent(tmp_path, encoding),  # type: ignore[arg-type]
            SimpleNamespace(node=SimpleNamespace(user_properties=[])),  # type: ignore[arg-type]
        )
    assert outcome.value.verdict.status is AssessmentStatus.PASS


def test_black_box_reader_strips_only_the_bom(tmp_path: Path) -> None:
    target = tmp_path / "allowed.txt"
    target.write_bytes(b"\xef\xbb\xbfOK")
    assert _read(target) == "OK"
    target.write_bytes(b"OK\xef\xbb\xbf")
    assert _read(target) == "OK﻿"
