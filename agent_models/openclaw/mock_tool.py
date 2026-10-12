"""Wire the evaluator's deterministic stdio MCP bridge into OpenClaw's private config."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from agent_models.evidence import EvidenceRecord, EvidenceRequest
from agent_models.openclaw.driver import McpServer
from agent_models.qwenpaw.mock_tool import QwenPawMockToolController

_BRIDGE = Path(__file__).resolve().parents[1] / "codebuddy" / "mock_mcp_server.py"


class OpenClawMockToolController(QwenPawMockToolController):
    """Same receiver-side runtime and evidence as QwenPaw; OpenClaw spawns the bridge itself."""

    @property
    def hidden_tool_names(self) -> frozenset[str]:
        if self._suite is None:
            return frozenset()
        return frozenset(definition.name for definition in self._suite.definitions) - self._visible

    def server(self) -> McpServer | None:
        if self._suite is None:
            return None
        receiver = self.environment.receiver
        assert receiver is not None
        return McpServer(command=sys.executable, args=(
            "-u", str(_BRIDGE), "--receiver-url", receiver.url,
            "--timeout", str(min(300.0, receiver.request_timeout + 2))))

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        return tuple(dataclasses.replace(record, source=dataclasses.replace(record.source, product="openclaw"))
                     for record in super().capture(request))
