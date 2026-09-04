"""Configure and observe deterministic CodeBuddy MCP mock tools."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from agent_models.evidence import EvidencePhase, EvidenceRecord, EvidenceRequest, JsonValue
from agent_models.tools import MockToolProfile


class CodeBuddyMockToolController:
    def __init__(self, *, workspace: Path) -> None:
        self.workspace = workspace
        self.profile: MockToolProfile | None = None
        self.log_path: Path | None = None
        self._extra_args: tuple[str, ...] = ()

    @property
    def extra_args(self) -> tuple[str, ...]:
        return self._extra_args

    def configure(self, profile: MockToolProfile, *, run_id: str) -> None:
        if self.profile is not None:
            raise RuntimeError("一个 Agent 会话只能配置一个 Mock Tool Profile")
        server_path = Path(__file__).with_name("mock_mcp_server.py").resolve()
        log_directory = self.workspace / ".agent_test_tool" / "mock_tool"
        log_directory.mkdir(parents=True, exist_ok=True)
        self.log_path = log_directory / f"{_safe_name(run_id)}.jsonl"
        self.profile = profile
        server = {
            "type": "stdio",
            "command": sys.executable,
            "args": [
                "-u",
                str(server_path),
                "--tool-name",
                profile.name,
                "--content-type",
                profile.content_type,
                "--body-json",
                json.dumps(profile.body, ensure_ascii=False),
                "--log-path",
                str(self.log_path),
            ],
        }
        config = json.dumps({"mcpServers": {"ats_mock": server}}, ensure_ascii=False)
        self._extra_args = ("--mcp-config", config, "--strict-mcp-config")

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        if request.phase is EvidencePhase.BEFORE or self.profile is None:
            return ()
        calls: list[JsonValue] = []
        if self.log_path is not None and self.log_path.is_file():
            for line in self.log_path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError("Mock Tool 调用日志包含无效 JSON") from error
                calls.append(item)
        return (
            EvidenceRecord(
                evidence_id="mock_tool_io",
                evidence_type="runtime_evidence",
                phase=request.phase,
                data={
                    "tool_name": self.profile.name,
                    "configured_return": {
                        "content_type": self.profile.content_type,
                        "body": self.profile.body,
                    },
                    "calls": calls,
                },
            ),
        )

    def close(self) -> None:
        if self.log_path is None:
            return
        directory = self.log_path.parent
        shutil.rmtree(directory, ignore_errors=True)


def _safe_name(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
    return safe[:180] or "run"
