"""Offline contract and real loopback MCP bridge tests for OpenCode."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_models import EvidencePhase, EvidenceRequest, MockToolProfile
from agent_models.environment.session import ControlledEnvironment
from agent_models.opencode.mock_tool import OpenCodeMockToolController
from agent_models.tools import ToolDefinition, ToolResponse, ToolSuite


@pytest.fixture
def environment(tmp_path: Path):
    with ControlledEnvironment(tmp_path / "workspace", evidence_directory=tmp_path / "evidence",
                               run_id="opencode-run", request_timeout=1) as env:
        yield env


def controller(environment, tmp_path: Path):
    return OpenCodeMockToolController(workspace=tmp_path / "workspace", environment=environment)


def request(phase: EvidencePhase = EvidencePhase.AFTER):
    return EvidenceRequest(sample_id="mock", prompt_id="01", repeat_index=1, phase=phase)


def suite(*names: str) -> ToolSuite:
    return ToolSuite(tuple(ToolDefinition(name=name, description="test", input_schema={"type": "object"},
                                          responses=(ToolResponse({"name": name}),)) for name in names))


def bridge(control, workspace: Path, tool: str):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": tool, "arguments": {"query": "probe"}}},
    ]
    completed = subprocess.run(control.mcp_config["ats_mock"]["command"], cwd=workspace,
                               input="".join(json.dumps(item) + "\n" for item in messages),
                               text=True, encoding="utf-8", capture_output=True, timeout=5, check=True)
    assert completed.stderr == ""
    return [json.loads(line) for line in completed.stdout.splitlines()]


def test_empty_controller(environment, tmp_path):
    control = controller(environment, tmp_path)
    assert control.mcp_config == {} and control.tools_config == {}
    assert control.capture(request()) == ()


def test_profile_preserves_evidence_scope_and_does_not_embed_body_in_command(environment, tmp_path):
    control = controller(environment, tmp_path)
    control.configure(MockToolProfile("lookup", "application/json", {"ok": True}), run_id="scenario")
    local = control.mcp_config["ats_mock"]
    assert local["type"] == "local" and local["enabled"] is True
    assert "mock_mcp_server.py" in local["command"][2]
    assert environment.receiver.url in local["command"]
    assert "{\"ok\": true}" not in " ".join(local["command"])
    assert control.capture(request(EvidencePhase.BEFORE)) == ()
    environment.runtime.call("lookup", {}, correlation_id="tester-baseline")
    responses = bridge(control, tmp_path / "workspace", "lookup")
    assert responses[1]["result"]["tools"][0]["name"] == "lookup"
    assert responses[2]["result"]["structuredContent"] == {"ok": True}
    record = control.capture(request())[0]
    assert record.evidence_id == "mock_tool_io"
    assert record.source.product == "opencode"
    assert record.correlation.run_id == environment.run_id
    assert record.correlation.session_ids == ()
    assert record.data["configured_return"]["body"] == {"ok": True}
    assert len(record.data["calls"]) == 1
    assert record.data["calls"][0]["call_index"] == 2
    assert record.data["calls"][0]["arguments"] == {"query": "probe"}
    assert record.data["calls"][0]["correlation_id"] != "tester-baseline"
    control.close()
    assert control.mcp_config == {}
    assert environment.receiver.health()["healthy"]


def test_suite_visibility_and_state(environment, tmp_path):
    control = controller(environment, tmp_path)
    control.configure_suite(suite("lookup", "sink"), run_id="scenario", initial_state={"count": 0},
                            visible_tool_names=frozenset({"lookup"}), max_turns=5)
    assert control.max_turns == 5
    assert control.tools_config == {"ats_mock_sink": False}
    assert environment.runtime.state == {"count": 0}
    assert {item["name"] for item in environment.runtime.list_tools()} == {"lookup", "sink"}
    copied = control.mcp_config
    copied["ats_mock"]["command"].clear()
    assert control.mcp_config["ats_mock"]["command"]
    assert len(bridge(control, tmp_path / "workspace", "lookup")[1]["result"]["tools"]) == 2
    assert len(control.capture(request())[0].data["calls"]) == 1


@pytest.mark.parametrize("name", ["--flag", "bad name", "bad\nname", "", "1lookup", "中文", "a" * 129, None])
def test_bad_names_rejected_without_opening_receiver(environment, tmp_path, name):
    control = controller(environment, tmp_path)
    with pytest.raises(ValueError, match="OpenCode tool names"):
        control.configure_suite(suite(name), run_id="scenario")
    assert environment.receiver is None and environment.runtime is None


def test_bad_visibility_and_turn_count_do_not_create_receiver(environment, tmp_path):
    control = controller(environment, tmp_path)
    with pytest.raises(ValueError, match="visible tool names are not configured"):
        control.configure_suite(suite("lookup"), run_id="scenario", visible_tool_names=frozenset({"missing"}))
    with pytest.raises(ValueError, match="max_turns"):
        control.configure_suite(suite("lookup"), run_id="scenario", max_turns=True)
    assert environment.receiver is None and environment.runtime is None


def test_second_configuration_rejected(environment, tmp_path):
    control = controller(environment, tmp_path)
    control.configure_suite(suite("lookup"), run_id="scenario")
    with pytest.raises(RuntimeError, match="only one Mock Tool Suite"):
        control.configure_suite(suite("other"), run_id="scenario")
