"""Verify the real local stdio-to-HTTP controlled-tool bridge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_models import EvidencePhase, EvidenceRequest, MockToolProfile
from agent_models.codebuddy import mock_mcp_server
from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
from agent_models.environment.ledger import EvidenceLedger
from agent_models.environment.receiver import HttpToolReceiver
from agent_models.environment.tool_runtime import ToolRuntime
from agent_models.tools import ToolDefinition, ToolEffect, ToolResponse, ToolSuite


class LocalEnvironment:
    """Exercise real runtime, HTTP and persistent ledger without a product CLI."""

    def __init__(self, root: Path) -> None:
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.ledger = EvidenceLedger(root / "evidence", run_id="parent-run", workspace=self.workspace)
        self.runtime = None
        self.receiver = None

    def configure_tools(self, suite, *, initial_state=None) -> None:
        if self.runtime is not None:
            raise RuntimeError("already configured")
        self.runtime = ToolRuntime(suite, initial_state=initial_state, event_sink=self.ledger.record)
        self.receiver = HttpToolReceiver(self.runtime, event_sink=self.ledger.record, request_timeout=0.5)

    def close(self) -> None:
        if self.receiver:
            self.receiver.close()
        self.ledger.close()


@pytest.fixture
def environment(tmp_path):
    env = LocalEnvironment(tmp_path)
    try:
        yield env
    finally:
        env.close()


def initialize(version="2025-06-18"):
    return [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "test", "version": "1"},
    }}, {"jsonrpc": "2.0", "method": "notifications/initialized"}]


def rpc(method, params=None, request_id=2):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def run_server(environment, messages, *, raw_input=None, timeout=4):
    completed = subprocess.run((sys.executable, "-u", str(Path(mock_mcp_server.__file__).resolve()),
        "--receiver-url", environment.receiver.url, "--timeout", "1"),
        input=raw_input if raw_input is not None else "".join(json.dumps(x) + "\n" for x in messages),
        cwd=environment.workspace, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        check=True)
    assert completed.stderr == ""
    return [json.loads(line) for line in completed.stdout.splitlines()]


def controller(environment):
    return CodeBuddyMockToolController(workspace=environment.workspace, environment=environment)


def capture_request(phase=EvidencePhase.AFTER):
    return EvidenceRequest(sample_id="ATS-5.1b-D5-02-S05", prompt_id="TOOL-INJECTION-01", repeat_index=1, phase=phase)


class TestCodeBuddyMockMcpServer:
    @pytest.mark.parametrize("name", ["--max-turns", "-flag", "bad name", "bad\nname", "bad\x00name",
                                       "", "1lookup", ".lookup", "中文", "a" * 129, None])
    def test_controller_rejects_unsafe_cli_tool_names_before_environment_creation(self, environment, name) -> None:
        control = controller(environment)
        suite = ToolSuite((ToolDefinition(name, "test", {"type": "object"}, (ToolResponse("ok"),)),))
        with pytest.raises(ValueError, match="CodeBuddy tool names"):
            control.configure_suite(suite, run_id="r")
        assert environment.receiver is None
        assert environment.runtime is None
        assert control.extra_args == ()

    @pytest.mark.parametrize("name", ["MOCK_LOOKUP_TOOL", "lookup", "_private_tool", "tool.v1-test", "a" * 128])
    def test_controller_accepts_safe_legacy_and_portable_tool_names(self, environment, name) -> None:
        control = controller(environment)
        control.configure(MockToolProfile(name, "text/plain", "ok"), run_id="r")
        assert name in control.extra_args
        assert f"mcp__ats_mock__{name}" in control.extra_args

    def test_lists_and_calls_configured_tool_through_real_socket(self, environment) -> None:
        control = controller(environment)
        body = {"status": "ok", "records": [], "message": "中文"}
        control.configure(MockToolProfile("MOCK_LOOKUP_TOOL", "application/json", body), run_id="scenario-run")
        responses = run_server(environment, initialize() + [rpc("tools/list"), rpc("tools/call", {
            "name": "MOCK_LOOKUP_TOOL", "arguments": {"query": ""}}, 3)])
        assert responses[1]["result"]["tools"][0]["name"] == "MOCK_LOOKUP_TOOL"
        assert responses[2]["result"]["structuredContent"] == body
        wire = responses[2]["result"]["_meta"]["agenttesttool/correlation_id"]
        events = environment.ledger.events
        assert any(e["source"] == "tool_runtime" and e["kind"] == "completed" and e["correlation_id"] == wire for e in events)
        assert any(e["source"] == "http_receiver" and e["kind"] == "http_received" and e["correlation_id"] == wire for e in events)
        assert environment.ledger.run_id == "parent-run"
        assert any(e["data"].get("scenario_run_id") == "scenario-run" for e in events)

    def test_multi_tool_state_and_sequences_survive_new_stdio_process(self, environment) -> None:
        suite = ToolSuite((
            ToolDefinition("update", "Update simulated state", {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
                (ToolResponse("first", effects=(ToolEffect("append", "values", argument_path=("value",)),)),
                 ToolResponse("injection", effects=(ToolEffect("increment", "calls", 1),)))),
            ToolDefinition("status", "Return stable result", {"type": "object"}, (ToolResponse({"ready": True}),)),
        ))
        control = controller(environment)
        control.configure_suite(suite, run_id="scenario", initial_state={"values": ["initial"], "calls": 10})
        first = run_server(environment, initialize() + [rpc("tools/list"), rpc("tools/call", {"name": "update", "arguments": {"value": "one"}}, 3)])
        assert len(first[1]["result"]["tools"]) == 2
        assert first[2]["result"]["content"][0]["text"] == "first"
        second = run_server(environment, initialize() + [rpc("tools/call", {"name": "update", "arguments": {"value": "two"}}), rpc("tools/call", {"name": "status"}, 3)])
        assert second[1]["result"]["content"][0]["text"] == "injection"
        assert second[2]["result"]["structuredContent"] == {"ready": True}
        assert environment.runtime.state == {"values": ["initial", "one"], "calls": 11}
        assert environment.runtime.snapshot().call_counts == {"update": 2, "status": 1}
        evidence = control.capture(capture_request())[0].data
        assert evidence["tool_names"] == ["update", "status"] and len(evidence["calls"]) == 3

    def test_legacy_capture_excludes_direct_runtime_baseline(self, environment) -> None:
        control = controller(environment)
        control.configure(MockToolProfile("lookup", "text/plain", "result"), run_id="scenario")
        environment.runtime.call("lookup", {}, correlation_id="baseline")
        run_server(environment, initialize() + [rpc("tools/call", {"name": "lookup"})])
        evidence = control.capture(capture_request())[0].data
        assert len(evidence["calls"]) == 1
        assert evidence["calls"][0]["call_index"] == 2
        assert evidence["calls"][0]["correlation_id"] != "baseline"
        assert evidence["observation_scope"] == (
            "requests received by evaluator-controlled endpoint; caller identity not authenticated"
        )

    def test_controller_preserves_legacy_evidence_and_never_puts_body_or_logs_in_argv(self, environment) -> None:
        control = controller(environment)
        control.configure(MockToolProfile("MOCK_LOOKUP_TOOL", "text/plain", "unique-fixture-body"), run_id="test-run")
        assert control.extra_args[control.extra_args.index("--tools") + 1] == "ToolSearch"
        assert "mcp__ats_mock__MOCK_LOOKUP_TOOL" in control.extra_args
        config = json.loads(control.extra_args[control.extra_args.index("--mcp-config") + 1])
        server = config["mcpServers"]["ats_mock"]
        assert server["type"] == "stdio" and "--receiver-url" in server["args"]
        assert not any(token in str(server) for token in ("unique-fixture-body", "--body-json", "--log-path"))
        assert control.capture(capture_request(EvidencePhase.BEFORE)) == ()
        run_server(environment, initialize() + [rpc("tools/call", {"name": "MOCK_LOOKUP_TOOL", "arguments": {"query": ""}})])
        record = control.capture(capture_request())[0]
        assert record.evidence_id == "mock_tool_io"
        assert record.data["tool_name"] == "MOCK_LOOKUP_TOOL"
        assert record.data["configured_return"] == {"body": "unique-fixture-body", "content_type": "text/plain"}
        assert record.data["calls"][0]["body"] == "unique-fixture-body"
        assert not record.data["calls"][0]["result"]["isError"]
        assert not list(environment.workspace.iterdir())
        evidence_path = environment.ledger.directory / "events.jsonl"
        recorded = evidence_path.read_bytes()
        control.close()
        assert control.extra_args == () and evidence_path.read_bytes() == recorded
        assert environment.receiver.health()["healthy"]

    def test_error_response_is_tool_error_and_does_not_apply_effects(self, environment) -> None:
        environment.configure_tools(ToolSuite((ToolDefinition("error", "Fail", {"type": "object"}, (
            ToolResponse({"reason": "fixture failure"}, is_error=True, effects=(ToolEffect("set", "sent", True),)),)),)))
        result = run_server(environment, initialize() + [rpc("tools/call", {"name": "error"})])[1]["result"]
        assert result["isError"] and result["structuredContent"] == {"reason": "fixture failure"}
        assert environment.runtime.state == {}
        assert environment.receiver.health()["healthy"]

    def test_invalid_arguments_unknown_tool_and_method_are_protocol_errors(self, environment) -> None:
        controller(environment).configure(MockToolProfile("lookup", "text/plain", "ok"), run_id="r")
        responses = run_server(environment, initialize() + [rpc("tools/call", {"name": "missing"}),
            rpc("tools/call", {"name": "lookup", "arguments": []}, 3),
            rpc("tools/call", {"name": "lookup", "arguments": {"query": 9}}, 4), rpc("not/method", {}, 5)])
        assert [r["error"]["code"] for r in responses[1:]] == [-32602, -32602, -32602, -32601]
        assert not any(e["kind"] == "completed" for e in environment.runtime.events)

    def test_parse_errors_notifications_and_initialization_state(self, environment) -> None:
        controller(environment).configure(MockToolProfile("lookup", "text/plain", "ok"), run_id="r")
        before = [rpc("tools/list"), rpc("initialize", {}), rpc("ping", {}, 9)]
        messages = before + initialize() + [{"jsonrpc": "2.0", "method": "notifications/ignored"}, rpc("tools/list", {}, 8)]
        responses = run_server(environment, (), raw_input="not-json\n[]\n" + "".join(json.dumps(x) + "\n" for x in messages))
        assert [r.get("error", {}).get("code") for r in responses[:4]] == [-32700, -32600, -32600, -32602]
        assert responses[4] == {"jsonrpc": "2.0", "id": 9, "result": {}}
        assert responses[-1]["result"]["tools"][0]["name"] == "lookup"

    @pytest.mark.parametrize("requested,negotiated,structured", [("2025-06-18", "2025-06-18", True), ("2024-11-05", "2024-11-05", False), ("unsupported", "2025-06-18", True)])
    def test_negotiates_only_supported_versions(self, environment, requested, negotiated, structured) -> None:
        controller(environment).configure(MockToolProfile("lookup", "application/json", {"answer": 1}), run_id="r")
        responses = run_server(environment, initialize(requested) + [rpc("tools/call", {"name": "lookup"})])
        assert responses[0]["result"]["protocolVersion"] == negotiated
        assert ("structuredContent" in responses[1]["result"]) is structured
        assert json.loads(responses[1]["result"]["content"][0]["text"]) == {"answer": 1}

    def test_receiver_timeout_returns_protocol_failure_without_success(self, environment) -> None:
        environment.configure_tools(ToolSuite((ToolDefinition("wait", "wait", {"type": "object"}, (ToolResponse("never", gate="release"),)),)))
        responses = run_server(environment, initialize() + [rpc("tools/call", {"name": "wait"})])
        assert responses[1]["error"]["code"] == -32603
        assert environment.runtime.state == {}
        assert any(e["kind"] == "failed" for e in environment.runtime.events)

    def test_exhaustion_is_protocol_failure_not_business_success(self, environment) -> None:
        control = controller(environment)
        control.configure_suite(ToolSuite((ToolDefinition("once", "once", {"type": "object"},
            (ToolResponse("only", effects=(ToolEffect("increment", "count", 1),)),)),)), run_id="r")
        responses = run_server(environment, initialize() + [rpc("tools/call", {"name": "once"}),
            rpc("tools/call", {"name": "once"}, 3)])
        assert responses[1]["result"]["isError"] is False
        assert responses[2]["error"]["code"] == -32603
        assert environment.runtime.state == {"count": 1}
        assert len(control.capture(capture_request())[0].data["calls"]) == 1

    def test_closed_receiver_returns_protocol_error_without_traceback(self, environment) -> None:
        controller(environment).configure(MockToolProfile("lookup", "text/plain", "ok"), run_id="r")
        environment.receiver.close()
        responses = run_server(environment, initialize() + [rpc("tools/list")])
        assert responses[1]["error"]["code"] == -32603
        assert environment.receiver.url not in str(responses)

    def test_malformed_surrogate_id_cannot_crash_stdio(self, environment) -> None:
        controller(environment).configure(MockToolProfile("lookup", "text/plain", "ok"), run_id="r")
        responses = run_server(environment, [rpc("ping", request_id="\ud800")])
        assert responses[0]["result"] == {}

    def test_reconfiguration_is_rejected(self, environment) -> None:
        control = controller(environment)
        profile = MockToolProfile("lookup", "text/plain", "ok")
        control.configure(profile, run_id="r")
        with pytest.raises(RuntimeError):
            control.configure(profile, run_id="r2")

    @pytest.mark.parametrize("url", ["https://127.0.0.1:123/a", "http://localhost:123/a", "http://example.com:123/a", "http://127.0.0.1:123/", "http://user:pass@127.0.0.1:123/a", "http://127.0.0.1:123/a?query=x"])
    def test_bridge_rejects_nonlocal_or_ambiguous_endpoint(self, url) -> None:
        with pytest.raises(ValueError):
            mock_mcp_server.HttpBridge(url)
