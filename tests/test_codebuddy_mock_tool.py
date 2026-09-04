"""Verify deterministic CodeBuddy MCP mock-tool behavior."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agent_models import (
    EvidencePhase,
    EvidenceRequest,
    MockToolProfile,
    RequestContext,
)
from agent_models.codebuddy import mock_mcp_server
from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController


class TestCodeBuddyMockMcpServer:
    def test_lists_and_calls_configured_tool(self, tmp_path) -> None:
        log_path = tmp_path / "calls.jsonl"
        body = {"status": "ok", "records": []}
        messages = (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "MOCK_LOOKUP_TOOL", "arguments": {"query": ""}},
            },
        )
        completed = subprocess.run(
            (
                sys.executable,
                str(Path(mock_mcp_server.__file__).resolve()),
                "--tool-name",
                "MOCK_LOOKUP_TOOL",
                "--content-type",
                "application/json",
                "--body-json",
                json.dumps(body),
                "--log-path",
                str(log_path),
            ),
            input="".join(json.dumps(item) + "\n" for item in messages),
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )

        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        assert responses[1]["result"]["tools"][0]["name"] == "MOCK_LOOKUP_TOOL"
        assert responses[2]["result"]["structuredContent"] == body
        calls = [json.loads(line) for line in log_path.read_text().splitlines()]
        assert calls == [
            {
                "tool_name": "MOCK_LOOKUP_TOOL",
                "arguments": {"query": ""},
                "content_type": "application/json",
                "body": body,
                "result": responses[2]["result"],
            }
        ]

    def test_controller_exposes_mock_tool_io_evidence(self, tmp_path) -> None:
        controller = CodeBuddyMockToolController(workspace=tmp_path)
        profile = MockToolProfile("MOCK_LOOKUP_TOOL", "text/plain", "fixed result")
        controller.configure(profile, run_id="test-run")
        assert controller.log_path is not None
        controller.log_path.write_text(
            json.dumps(
                {
                    "tool_name": "MOCK_LOOKUP_TOOL",
                    "arguments": {"query": ""},
                    "content_type": "text/plain",
                    "body": "fixed result",
                    "result": {"isError": False},
                }
            )
            + "\n"
        )

        records = controller.capture(
            EvidenceRequest(
                sample_id="ATS-5.1b-D5-02-S05",
                prompt_id="TOOL-INJECTION-01",
                repeat_index=1,
                phase=EvidencePhase.AFTER,
                context=RequestContext(
                    "Bearer test",
                    "user-a",
                    "instance-a",
                    "test-run",
                ),
            )
        )

        assert records[0].evidence_id == "mock_tool_io"
        assert records[0].data["calls"][0]["body"] == "fixed result"
