"""Verify fail-closed assertions over local, explicitly scoped evidence."""

import copy
import http.client
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from agent_models.environment.ledger import EvidenceLedger
from agent_models.environment.receiver import HttpToolReceiver
from agent_models.environment.tool_runtime import ToolRuntime
from agent_models.tools import ToolDefinition, ToolEffect, ToolResponse, ToolSuite
from assertions.environment import (
    ObservationWindow,
    assert_collector_healthy,
    assert_event_order,
    assert_no_tool_calls,
    assert_simulated_effect,
    assert_simulated_state,
    assert_tool_arguments,
    assert_tool_call_count,
)


def _window(tmp_path: Path) -> tuple[EvidenceLedger, ObservationWindow]:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    ledger.record("http_receiver", "health_probe", {"healthy": True})
    ledger.record("http_receiver", "http_received", {"method": "POST", "route": "/call"}, "baseline")
    ledger.record("tool_runtime", "received", {"tool_name": "read", "arguments": {}}, "baseline")
    ledger.record("tool_runtime", "completed", {"tool_name": "read", "is_error": False}, "baseline")
    ledger.record("http_receiver", "http_responded", {"name": "read"}, "baseline")
    start = ledger.record("environment", "observation_started", {"tool_name": "read"})
    ledger.record("tool_runtime", "received", {"tool_name": "other", "arguments": {"id": 1}}, "other-call")
    end = ledger.record("environment", "observation_ended", {"tool_name": "read"})
    ledger.record("http_receiver", "health_probe", {"healthy": True})
    return ledger, ObservationWindow("run-test", start["sequence"], end["sequence"], "baseline")


def test_zero_calls_requires_a_healthy_scoped_window_and_normal_baseline(tmp_path: Path) -> None:
    ledger, window = _window(tmp_path)
    assert_no_tool_calls(ledger, "read", window=window)
    assert_tool_call_count(ledger, "read", 0, window=window)
    # The conclusion concerns only read; other received operations still exist.
    assert_tool_call_count(ledger, "other", 1, window=window)
    assert_tool_arguments(ledger, "other", {"id": 1}, window=window)


@pytest.mark.parametrize("mutation", ["no_baseline", "failed_baseline", "wrong_baseline_tool", "no_initial_probe", "no_final_probe", "target_called", "wrong_run", "unhealthy", "truncated", "reordered",
    "direct_runtime_baseline", "wrong_http_method", "wrong_http_route", "missing_http_response", "wrong_response_tool",
    "wrong_http_correlation", "http_response_before_completion", "arbitrary_start", "arbitrary_end", "wrong_window_tool"])
def test_zero_calls_rejects_incomplete_or_negative_evidence(tmp_path: Path, mutation: str) -> None:
    ledger, window = _window(tmp_path)
    events, health = ledger.events, ledger.health()
    if mutation == "no_baseline":
        events[3]["kind"] = "unrelated"
    elif mutation == "failed_baseline":
        events[3]["kind"] = "failed"
    elif mutation == "wrong_baseline_tool":
        events[3]["data"]["tool_name"] = "another"
    elif mutation == "no_initial_probe":
        events[0]["data"]["healthy"] = False
    elif mutation == "no_final_probe":
        events[-1]["kind"] = "unrelated"
    elif mutation == "target_called":
        events[6]["data"]["tool_name"] = "read"
    elif mutation == "wrong_run":
        events[0]["run_id"] = "other-run"
    elif mutation == "unhealthy":
        health["healthy"] = False
    elif mutation == "truncated":
        events.pop()
    elif mutation == "direct_runtime_baseline":
        events[1]["kind"] = events[4]["kind"] = "unrelated"
    elif mutation == "wrong_http_method":
        events[1]["data"]["method"] = "GET"
    elif mutation == "wrong_http_route":
        events[1]["data"]["route"] = "/health"
    elif mutation == "missing_http_response":
        events[4]["kind"] = "unrelated"
    elif mutation == "wrong_response_tool":
        events[4]["data"]["name"] = "other"
    elif mutation == "wrong_http_correlation":
        events[1]["correlation_id"] = "unrelated"
    elif mutation == "http_response_before_completion":
        events[3], events[4] = events[4], events[3]
        events[3]["sequence"], events[4]["sequence"] = 4, 5
    elif mutation == "arbitrary_start":
        events[5]["kind"] = "unrelated"
    elif mutation == "arbitrary_end":
        events[7]["source"] = "another_component"
    elif mutation == "wrong_window_tool":
        events[5]["data"]["tool_name"] = "other"
    else:
        events[1], events[2] = events[2], events[1]
    with pytest.raises(AssertionError):
        assert_no_tool_calls(events, "read", window=window, health=health)


def test_empty_collection_and_unfinished_window_do_not_prove_absence(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    with pytest.raises(AssertionError, match="完整观察窗口"):
        assert_tool_call_count(ledger, "read", 0)
    with pytest.raises(AssertionError):
        assert_no_tool_calls(ledger, "read", window=ObservationWindow("run-test", 1, 2, "baseline"))
    ledger.record("environment", "observation_started", {})
    with pytest.raises(AssertionError, match="尚未结束"):
        assert_no_tool_calls(ledger, "read", window=ObservationWindow("run-test", 1, 2, "baseline"))


def test_health_requires_explicit_success_and_error_list() -> None:
    assert_collector_healthy({"healthy": True, "errors": []})
    for value in [None, {}, {"healthy": 1, "errors": []}, {"healthy": True}, {"healthy": True, "errors": ["lost event"]}]:
        with pytest.raises(AssertionError):
            assert_collector_healthy(value)


def test_argument_assertion_is_exact_and_requires_unambiguous_call(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    ledger.record("tool_runtime", "received", {"tool_name": "write", "arguments": {"count": 1}}, "call-1")
    assert_tool_arguments(ledger, "write", {"count": 1})
    with pytest.raises(AssertionError):
        assert_tool_arguments(ledger, "write", {"count": True})
    ledger.record("tool_runtime", "received", {"tool_name": "write", "arguments": {"count": 2}}, "call-2")
    with pytest.raises(AssertionError, match="不唯一"):
        assert_tool_arguments(ledger, "write", {"count": 1})
    assert_tool_arguments(ledger, "write", {"count": 2}, correlation_id="call-2")
    assert_tool_call_count(ledger, "write", 2)


def test_redacted_values_cannot_be_used_to_assert_original_arguments(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    ledger.record("tool_runtime", "received", {"tool_name": "write", "arguments": {"token": "FAKE-TOKEN"}}, "call-1")
    with pytest.raises(AssertionError, match="脱敏"):
        assert_tool_arguments(ledger, "write", {"token": "[REDACTED]"})


def test_effects_require_matching_local_state_values_and_complete_lifecycle(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    ledger.record("tool_runtime", "received", {"tool_name": "write", "arguments": {}}, "call-1")
    ledger.record("tool_runtime", "side_effect", {"tool_name": "write", "key": "count", "before": 0, "after": 1}, "call-1")
    with pytest.raises(AssertionError, match="完整调用"):
        assert_simulated_effect(ledger, "write", "count", 0, 1)
    ledger.record("tool_runtime", "completed", {"tool_name": "write", "is_error": False}, "call-1")
    assert_simulated_effect(ledger, "write", "count", 0, 1)
    assert_simulated_state({"count": 1}, {"count": 1})
    with pytest.raises(AssertionError):
        assert_simulated_effect(ledger, "write", "count", 0, 2)
    with pytest.raises(AssertionError):
        assert_simulated_state({"count": 1}, {"count": True})


def test_event_order_is_local_to_one_collector_run_and_correlated_operation(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    ledger.record("tool_runtime", "received", {}, "call-1")
    ledger.record("tool_runtime", "completed", {}, "call-1")
    ledger.record("tool_runtime", "received", {}, "call-2")
    assert_event_order(ledger, 1, 2)
    with pytest.raises(AssertionError):
        assert_event_order(ledger, 2, 1)
    with pytest.raises(AssertionError, match="不同操作"):
        assert_event_order(ledger, 1, 3)
    events = copy.deepcopy(ledger.events)
    events[1]["run_id"] = "another-run"
    with pytest.raises(AssertionError, match="不同运行"):
        assert_event_order(events, 1, 2, health=ledger.health())


@pytest.mark.parametrize("start,end", [(0, 2), (1, 1), (2, 1), (True, 2)])
def test_window_rejects_invalid_boundaries(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        ObservationWindow("run", start, end, "baseline")


def test_assertions_integrate_with_real_loopback_receiver_and_runtime(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    suite = ToolSuite((ToolDefinition("read", "Read synthetic resource", {"type": "object"},
                                    (ToolResponse("ok", effects=(ToolEffect("increment", "calls", 1),)),)),))
    runtime = ToolRuntime(suite, event_sink=ledger.record)
    with HttpToolReceiver(runtime, event_sink=ledger.record) as receiver:
        url = urlsplit(receiver.url)
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=2)
        try:
            connection.request("POST", url.path + "/call", json.dumps({"name": "read", "arguments": {}}),
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            assert response.status == 200
            baseline_id = json.loads(response.read())["correlation_id"]
        finally:
            connection.close()
        assert_simulated_state(runtime.state, {"calls": 1})
        assert_simulated_effect(ledger, "read", "calls", None, 1, correlation_id=baseline_id)
        with receiver.paused():
            start = ledger.record("environment", "observation_started", {"tool_name": "read"})
        end = ledger.record("environment", "observation_ended", {"tool_name": "read"})
        receiver.probe()
        window = ObservationWindow(ledger.run_id, start["sequence"], end["sequence"], baseline_id)
        assert_no_tool_calls(ledger, "read", window=window)
    assert ledger.close()["healthy"]


def test_real_direct_runtime_baseline_plus_socket_probes_is_insufficient(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    runtime = ToolRuntime(ToolSuite((ToolDefinition("read", "Read synthetic resource", {"type": "object"},
        (ToolResponse("ok"),)),)), event_sink=ledger.record)
    with HttpToolReceiver(runtime, event_sink=ledger.record) as receiver:
        runtime.call("read", {}, correlation_id="direct-baseline")
        start = ledger.record("environment", "observation_started", {"tool_name": "read"})
        end = ledger.record("environment", "observation_ended", {"tool_name": "read"})
        receiver.probe()
        window = ObservationWindow(ledger.run_id, start["sequence"], end["sequence"], "direct-baseline")
        with pytest.raises(AssertionError, match="实际 HTTP"):
            assert_no_tool_calls(ledger, "read", window=window)
    ledger.close()
