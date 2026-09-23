"""Connect deterministic evaluator-owned MCP tools to OpenCode."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Protocol

from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    JsonValue,
)
from agent_models.environment.receiver import HttpToolReceiver
from agent_models.environment.tool_runtime import ToolRuntime
from agent_models.tools import MockToolProfile, ToolDefinition, ToolResponse, ToolSuite


class _Ledger(Protocol):
    run_id: str

    @property
    def events(self) -> list[dict[str, JsonValue]]: ...

    def record(
        self, source: str, kind: str, data: JsonValue,
        correlation_id: str | None = None,
    ) -> object: ...

    def redact(self, data: JsonValue) -> JsonValue: ...


class _Environment(Protocol):
    runtime: ToolRuntime | None
    receiver: HttpToolReceiver | None
    ledger: _Ledger

    def configure_tools(
        self, suite: ToolSuite, *, initial_state: dict[str, JsonValue] | None = None,
    ) -> None: ...


class OpenCodeMockToolController:
    """Build OpenCode's local MCP config without placing tool bodies in argv.

    The OpenCode driver owns the config directory and process lifecycle. This
    controller owns neither a subprocess nor the evaluator's tool receiver.
    """

    def __init__(self, *, workspace: Path, environment: _Environment) -> None:
        self.workspace = workspace
        self.environment = environment
        self.profile: MockToolProfile | None = None
        self._suite: ToolSuite | None = None
        self._mcp_config: dict[str, JsonValue] = {}
        self._tools_config: dict[str, bool] = {}
        self._max_turns: int = 4

    @property
    def mcp_config(self) -> dict[str, JsonValue]:
        """Contents of the per-run OpenCode configuration's ``mcp`` field."""
        return copy.deepcopy(self._mcp_config)

    @property
    def tools_config(self) -> dict[str, bool]:
        """Per-run tool visibility settings to merge into ``tools``."""
        return dict(self._tools_config)

    @property
    def max_turns(self) -> int:
        """Caller-enforced turn limit (OpenCode MCP config has no turn limit)."""
        return self._max_turns

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
        visible_tool_names: frozenset[str] | None = None,
        max_turns: int = 4,
    ) -> None:
        if self._suite is not None:
            raise RuntimeError("one Agent session can configure only one Mock Tool Suite")
        if type(max_turns) is not int or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        for definition in suite.definitions:
            if not isinstance(definition.name, str) or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.-]{0,127}", definition.name,
            ) is None:
                raise ValueError("OpenCode tool names must match [A-Za-z_][A-Za-z0-9_.-]{0,127}")
        configured_names = frozenset(definition.name for definition in suite.definitions)
        visible_names = configured_names if visible_tool_names is None else visible_tool_names
        unknown_visible = visible_names - configured_names
        if unknown_visible:
            raise ValueError("visible tool names are not configured: " + ", ".join(sorted(unknown_visible)))

        self.environment.configure_tools(suite, initial_state=initial_state)
        receiver, runtime = self.environment.receiver, self.environment.runtime
        if receiver is None or runtime is None:
            raise RuntimeError("controlled tool environment is not initialized")

        server_path = Path(__file__).resolve().parents[1] / "codebuddy" / "mock_mcp_server.py"
        self._mcp_config = {"ats_mock": {
            "type": "local",
            "command": [
                sys.executable, "-u", str(server_path),
                "--receiver-url", receiver.url,
                "--timeout", str(min(300.0, receiver.request_timeout + 2)),
            ],
            "enabled": True,
        }}
        self._tools_config = {
            f"ats_mock_{name}": False for name in configured_names - visible_names
        }
        self._suite = copy.deepcopy(suite)
        self._max_turns = max_turns
        self.environment.ledger.record("mock_tool", "configured", {
            "scenario_run_id": run_id,
            "tool_names": [item["name"] for item in runtime.list_tools()],
            "visible_tool_names": sorted(visible_names),
        })

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        if request.phase is EvidencePhase.BEFORE or self._suite is None:
            return ()
        runtime = self.environment.runtime
        if runtime is None:
            raise RuntimeError("controlled tool runtime is unavailable")
        received = {
            event["correlation_id"] for event in self.environment.ledger.events
            if event["source"] == "http_receiver" and event["kind"] == "http_received"
        }
        calls: list[JsonValue] = []
        for event in runtime.events:
            if event["correlation_id"] not in received or event["kind"] not in {"completed", "failed"}:
                continue
            data = event["data"]
            if "body" not in data:
                continue
            body = data["body"]
            result: dict[str, JsonValue] = {
                "content": [{"type": "text", "text": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)}],
                "isError": data["is_error"],
            }
            if data["content_type"] == "application/json" and isinstance(body, dict):
                result["structuredContent"] = body
            calls.append({
                "tool_name": data["tool_name"], "arguments": data["arguments"],
                "content_type": data["content_type"], "body": body,
                "result": result, "correlation_id": event["correlation_id"],
                "call_index": data["call_index"],
            })
        if self.profile is not None:
            capture: dict[str, JsonValue] = {
                "tool_name": self.profile.name,
                "configured_return": {"content_type": self.profile.content_type, "body": self.profile.body},
                "calls": calls,
            }
        else:
            capture = {
                "tool_names": [definition.name for definition in self._suite.definitions],
                "calls": calls, "configured_tools": runtime.list_tools(),
            }
        capture["observation_scope"] = (
            "requests received by evaluator-controlled endpoint; caller identity not authenticated"
        )
        return (EvidenceRecord(
            evidence_id="mock_tool_io", evidence_type="runtime_evidence", phase=request.phase,
            data=self.environment.ledger.redact(capture),
            source=EvidenceSource(
                provider="controlled_mock_tool", channel="stdio_mcp_to_local_http_receiver",
                authority=EvidenceAuthority.EVALUATOR_CONTROLLED, product="opencode",
            ),
            correlation=EvidenceCorrelation(run_id=self.environment.ledger.run_id),
            proves=("评测方接收端实际收到的模拟工具请求及其确定性结果",),
            limitations=("只覆盖评测方控制的工具端点，不证明产品其他通道没有调用或副作用。",),
        ),)

    def close(self) -> None:
        # AgentModel owns environment shutdown; evidence survives controller close.
        self._mcp_config = {}
        self._tools_config = {}
