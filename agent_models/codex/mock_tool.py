"""Wire the evaluator's deterministic stdio MCP bridge into Codex through `-c` overrides."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from agent_models.codex.driver import McpServer
from agent_models.evidence import EvidenceRecord, EvidenceRequest
from agent_models.qwenpaw.mock_tool import QwenPawMockToolController

_BRIDGE = Path(__file__).resolve().parents[1] / "codebuddy" / "mock_mcp_server.py"


class CodexMockToolController(QwenPawMockToolController):
    """Same receiver-side runtime and evidence as QwenPaw; Codex spawns the bridge itself."""

    def server(self) -> McpServer | None:
        if self._suite is None:
            return None
        receiver = self.environment.receiver
        assert receiver is not None
        return McpServer(
            command=sys.executable,
            args=("-u", str(_BRIDGE), "--receiver-url", receiver.url,
                  "--timeout", str(min(300.0, receiver.request_timeout + 2))),
            enabled_tools=tuple(sorted(self._visible)),
        )

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        return tuple(dataclasses.replace(record, source=dataclasses.replace(record.source, product="codex"))
                     for record in super().capture(request))
