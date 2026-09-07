"""Configure and observe deterministic CodeBuddy MCP mock tools."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Protocol

from agent_models.evidence import EvidencePhase, EvidenceRecord, EvidenceRequest, JsonValue
from agent_models.environment.receiver import HttpToolReceiver
from agent_models.environment.tool_runtime import ToolRuntime
from agent_models.tools import MockToolProfile, ToolDefinition, ToolResponse, ToolSuite


class _Ledger(Protocol):
    @property
    def events(self) -> list[dict[str, JsonValue]]: ...

    def record(self, source: str, kind: str, data: JsonValue,
               correlation_id: str | None = None) -> object: ...
    def redact(self, data: JsonValue) -> JsonValue: ...


class _Environment(Protocol):
    runtime: ToolRuntime | None
    receiver: HttpToolReceiver | None
    ledger: _Ledger

    def configure_tools(self, suite: ToolSuite, *, initial_state: dict[str, JsonValue] | None = None) -> None: ...


class CodeBuddyMockToolController:
    def __init__(self, *, workspace: Path, environment: _Environment) -> None:
        self.workspace = workspace
        self.environment = environment
        self.profile: MockToolProfile | None = None
        self._suite: ToolSuite | None = None
        self._extra_args: tuple[str, ...] = ()

    @property
    def extra_args(self) -> tuple[str, ...]:
        return self._extra_args

    def configure(self, profile: MockToolProfile, *, run_id: str) -> None:
        suite = ToolSuite((ToolDefinition(
            name=profile.name,
            description="Return a deterministic result from a controlled test environment.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}},
                          "additionalProperties": True},
            responses=(ToolResponse(body=profile.body, content_type=profile.content_type),),
        ),), exhaustion="repeat_last")
        self.configure_suite(suite, run_id=run_id)
        self.profile = copy.deepcopy(profile)

    def configure_suite(
        self, suite: ToolSuite, *, run_id: str,
        initial_state: dict[str, JsonValue] | None = None,
    ) -> None:
        if self._suite is not None:
            raise RuntimeError("一个 Agent 会话只能配置一个 Mock Tool Suite")
        # Names become CLI allow-list arguments, so reject flag-like tokens before
        # opening a receiver or altering the environment's tool configuration.
        for definition in suite.definitions:
            if not isinstance(definition.name, str) or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.-]{0,127}", definition.name
            ) is None:
                raise ValueError("CodeBuddy tool names must match [A-Za-z_][A-Za-z0-9_.-]{0,127}")
        self.environment.configure_tools(suite, initial_state=initial_state)
        receiver = self.environment.receiver
        runtime = self.environment.runtime
        if receiver is None or runtime is None:
            raise RuntimeError("受控工具环境未完成初始化")
        self.environment.ledger.record("mock_tool", "configured", {
            "scenario_run_id": run_id, "tool_names": [item["name"] for item in runtime.list_tools()],
        })
        server_path = Path(__file__).with_name("mock_mcp_server.py").resolve()
        server = {
            "type": "stdio",
            "command": sys.executable,
            "args": [
                "-u",
                str(server_path),
                "--receiver-url",
                receiver.url,
                "--timeout",
                str(min(300.0, receiver.request_timeout + 2)),
            ],
        }
        config = json.dumps({"mcpServers": {"ats_mock": server}}, ensure_ascii=False)
        self._extra_args = (
            "--mcp-config",
            config,
            "--strict-mcp-config",
            "--tools",
            "ToolSearch",
            "--allowedTools",
            "ToolSearch",
            *(str(item["name"]) for item in runtime.list_tools()),
            *(f"mcp__ats_mock__{item['name']}" for item in runtime.list_tools()),
            "--max-turns",
            "4",
        )
        self._suite = copy.deepcopy(suite)

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        if request.phase is EvidencePhase.BEFORE or self._suite is None:
            return ()
        calls: list[JsonValue] = []
        runtime = self.environment.runtime
        if runtime is None:
            raise RuntimeError("受控工具运行时不可用")
        received_correlations = {
            event["correlation_id"] for event in self.environment.ledger.events
            if event["source"] == "http_receiver" and event["kind"] == "http_received"
        }
        for event in runtime.events:
            if event["correlation_id"] not in received_correlations:
                continue
            if event["kind"] not in {"completed", "failed"}:
                continue
            data = event["data"]
            if "body" not in data:
                continue  # Protocol-invalid calls remain in the parent evidence ledger.
            body = data["body"]
            result: dict[str, JsonValue] = {
                "content": [{"type": "text", "text": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)}],
                "isError": data["is_error"],
            }
            if data["content_type"] == "application/json" and isinstance(body, dict):
                result["structuredContent"] = body
            calls.append({"tool_name": data["tool_name"], "arguments": data["arguments"],
                          "content_type": data["content_type"], "body": body, "result": result,
                          "correlation_id": event["correlation_id"], "call_index": data["call_index"]})
        if self.profile is not None:
            capture: dict[str, JsonValue] = {
                "tool_name": self.profile.name,
                "configured_return": {"content_type": self.profile.content_type, "body": self.profile.body},
                "calls": calls,
            }
        else:
            capture = {"tool_names": [d.name for d in self._suite.definitions], "calls": calls,
                       "configured_tools": runtime.list_tools()}
        capture["observation_scope"] = (
            "requests received by evaluator-controlled endpoint; caller identity not authenticated"
        )
        return (
            EvidenceRecord(
                evidence_id="mock_tool_io",
                evidence_type="runtime_evidence",
                phase=request.phase,
                data=self.environment.ledger.redact(capture),
            ),
        )

    def close(self) -> None:
        # AgentModel owns environment shutdown; evidence survives controller close.
        self._extra_args = ()
