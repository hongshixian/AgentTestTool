"""Register the evaluator's deterministic MCP bridge through QwenPaw's public MCP API."""

from __future__ import annotations

import copy
import json
import re
import sys
import time
from pathlib import Path

from agent_models.environment.session import ControlledEnvironment
from agent_models.evidence import (
    EvidenceAuthority, EvidenceCorrelation, EvidencePhase, EvidenceRecord, EvidenceRequest,
    EvidenceSource, JsonValue,
)
from agent_models.qwenpaw.client import MOCK_MCP_CLIENT_KEY, QwenPawClient
from agent_models.tools import MockToolProfile, ToolDefinition, ToolResponse, ToolSuite

_BRIDGE = Path(__file__).resolve().parents[1] / "codebuddy" / "mock_mcp_server.py"
_TOOL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}")


class QwenPawMockToolController:
    """Keep the tool runtime and receiver in the test process; QwenPaw only spawns the bridge."""

    def __init__(self, *, environment: ControlledEnvironment) -> None:
        self.environment = environment
        self.profile: MockToolProfile | None = None
        self._suite: ToolSuite | None = None
        self._visible: frozenset[str] = frozenset()

    @property
    def configured(self) -> bool:
        return self._suite is not None

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

    def configure_suite(self, suite: ToolSuite, *, run_id: str,
                        initial_state: dict[str, JsonValue] | None = None,
                        visible_tool_names: frozenset[str] | None = None) -> None:
        if self._suite is not None:
            raise RuntimeError("one Agent session can configure only one Mock Tool Suite")
        names = frozenset(definition.name for definition in suite.definitions)
        if any(not isinstance(name, str) or _TOOL_NAME.fullmatch(name) is None for name in names):
            raise ValueError("QwenPaw MCP tool names must match [A-Za-z_][A-Za-z0-9_.-]{0,127}")
        visible = names if visible_tool_names is None else visible_tool_names
        if visible - names:
            raise ValueError("visible tool names are not configured: " + ", ".join(sorted(visible - names)))
        self.environment.configure_tools(suite, initial_state=initial_state)
        if self.environment.receiver is None or self.environment.runtime is None:
            raise RuntimeError("controlled tool environment is not initialized")
        self.environment.ledger.register_secrets(secrets=(self.environment.receiver.url,))
        self._suite = copy.deepcopy(suite)
        self._visible = visible
        self.environment.ledger.record("mock_tool", "configured", {
            "scenario_run_id": run_id,
            "tool_names": [item["name"] for item in self.environment.runtime.list_tools()],
            "visible_tool_names": sorted(visible),
        })

    def register(self, client: QwenPawClient, *, timeout: float = 60.0) -> None:
        """Create the stdio MCP client and wait until QwenPaw lists exactly the visible tools."""
        if self._suite is None:
            return
        receiver = self.environment.receiver
        assert receiver is not None
        client.post("/api/mcp", {"client_key": MOCK_MCP_CLIENT_KEY, "client": {
            "name": MOCK_MCP_CLIENT_KEY, "enabled": True, "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", str(_BRIDGE), "--receiver-url", receiver.url,
                     "--timeout", str(min(300.0, receiver.request_timeout + 2))],
            "tools": sorted(self._visible),
        }})
        deadline = time.monotonic() + timeout
        listed: set[str] = set()
        while time.monotonic() < deadline:
            try:
                tools = client.get(f"/api/mcp/tools/{MOCK_MCP_CLIENT_KEY}")
            except RuntimeError:
                tools = None
            listed = {item.get("name") for item in tools or [] if isinstance(item, dict) and item.get("enabled", True)}
            if self._visible <= listed:
                self.environment.ledger.record("mock_tool", "registered", {"listed_tools": sorted(listed)})
                return
            time.sleep(1.0)
        raise TimeoutError(f"QwenPaw did not list mock tools {sorted(self._visible - listed)}")

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
                "content": [{"type": "text",
                             "text": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)}],
                "isError": data["is_error"],
            }
            if data["content_type"] == "application/json" and isinstance(body, dict):
                result["structuredContent"] = body
            calls.append({
                "tool_name": data["tool_name"], "arguments": data["arguments"],
                "content_type": data["content_type"], "body": body, "result": result,
                "correlation_id": event["correlation_id"], "call_index": data["call_index"],
            })
        if self.profile is not None:
            capture: dict[str, JsonValue] = {
                "tool_name": self.profile.name,
                "configured_return": {"content_type": self.profile.content_type, "body": self.profile.body},
                "calls": calls,
            }
        else:
            capture = {"tool_names": [definition.name for definition in self._suite.definitions],
                       "calls": calls, "configured_tools": runtime.list_tools()}
        capture["observation_scope"] = (
            "requests received by evaluator-controlled endpoint; caller identity not authenticated"
        )
        return (EvidenceRecord(
            evidence_id="mock_tool_io", evidence_type="runtime_evidence", phase=request.phase,
            data=self.environment.ledger.redact(capture),
            source=EvidenceSource(provider="controlled_mock_tool", channel="stdio_mcp_to_local_http_receiver",
                                  authority=EvidenceAuthority.EVALUATOR_CONTROLLED, product="qwenpaw"),
            correlation=EvidenceCorrelation(run_id=self.environment.ledger.run_id),
            proves=("评测方接收端实际收到的模拟工具请求及其确定性结果",),
            limitations=("只覆盖评测方控制的工具端点，不证明产品其他通道没有调用或副作用。",),
        ),)
