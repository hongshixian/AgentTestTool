"""Verify deterministic multi-tool responses, state and failure boundaries."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace

import pytest

from agent_models.environment.tool_runtime import (
    MAX_JSON_BYTES,
    RuntimeClosedError,
    RuntimeHealthError,
    ToolExhaustedError,
    ToolRuntime,
    ToolRuntimeError,
    ToolTimeoutError,
    ToolValidationError,
)
from agent_models.environment.orchestration import ScenarioRunner
from agent_models.tools import MockToolProfile, ToolDefinition, ToolEffect, ToolResponse, ToolSuite


def make_runtime(*responses: ToolResponse, exhaustion: str = "error", **kwargs) -> ToolRuntime:
    return ToolRuntime(ToolSuite((ToolDefinition("lookup", "Lookup synthetic data", {
        "type": "object", "properties": {"query": {"type": "string"}},
        "required": ["query"], "additionalProperties": False,
    }, responses),), exhaustion=exhaustion), **kwargs)


class TestToolRuntime:
    def test_legacy_profile_keeps_positional_contract(self) -> None:
        assert asdict(MockToolProfile("legacy", "text/plain", "ok")) == {
            "name": "legacy", "content_type": "text/plain", "body": "ok",
        }

    def test_lists_multiple_tools_and_injects_only_selected_call(self) -> None:
        schema = {"type": "object", "properties": {}, "additionalProperties": False}
        suite = ToolSuite((
            ToolDefinition("first", "First", schema, (ToolResponse("ok"), ToolResponse("injection"), ToolResponse("ok"))),
            ToolDefinition("second", "Second", schema, (ToolResponse({"value": 2}),)),
        ), exhaustion="repeat_last")
        runtime = ToolRuntime(suite)
        assert runtime.list_tools() == [
            {"name": "first", "description": "First", "inputSchema": schema},
            {"name": "second", "description": "Second", "inputSchema": schema},
        ]
        assert runtime.call("first", {}).body == "ok"
        assert runtime.call("second", {}).body == {"value": 2}
        assert [runtime.call("first", {}).body for _ in range(3)] == ["injection", "ok", "ok"]
        assert runtime.snapshot().call_counts == {"first": 4, "second": 1}

    def test_exhaustion_is_explicit_and_recorded(self) -> None:
        runtime = make_runtime(ToolResponse("only"))
        runtime.call("lookup", {"query": "a"})
        with pytest.raises(ToolExhaustedError):
            runtime.call("lookup", {"query": "b"})
        assert runtime.events[-1]["data"]["error_type"] == "ToolExhaustedError"
        assert runtime.healthy

    @pytest.mark.parametrize("arguments", [{}, {"query": 1}, {"query": "x", "extra": "forbidden"}, [], {1: "bad"}, {"query": float("nan")}, {"query": "x" * MAX_JSON_BYTES}])
    def test_invalid_arguments_are_failed_without_effects(self, arguments) -> None:
        runtime = make_runtime(ToolResponse("ok", effects=(ToolEffect("set", "called", True),)))
        with pytest.raises(ToolValidationError):
            runtime.call("lookup", arguments, correlation_id="bad-input")
        assert runtime.state == {}
        assert [e["kind"] for e in runtime.events] == ["received", "failed"]
        assert all(e["correlation_id"] == "bad-input" for e in runtime.events)
        assert runtime.snapshot().call_counts == {"lookup": 1}

    def test_schema_mismatch_retains_received_json_without_echoing_exception_values(self) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolValidationError) as caught:
            runtime.call("lookup", {"query": 12, "unsafe": "synthetic-marker"})
        assert "synthetic-marker" not in str(caught.value)
        assert runtime.events[0]["data"]["arguments"]["unsafe"] == "synthetic-marker"

    def test_supported_schema_subset_and_strict_boolean_numbers(self) -> None:
        schema = {"type": "object", "properties": {
            "values": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "integer", "minimum": 0, "maximum": 2}},
            "choice": {"enum": [{"flag": 1}]}, "fixed": {"const": "yes"},
            "text": {"type": "string", "minLength": 1, "maxLength": 3},
        }, "required": ["values", "choice", "fixed", "text"], "additionalProperties": False}
        runtime = ToolRuntime(ToolSuite((ToolDefinition("test", "test", schema, (ToolResponse("ok"),)),), "repeat_last"))
        good = {"values": [1], "choice": {"flag": 1}, "fixed": "yes", "text": "ok"}
        assert runtime.call("test", good).body == "ok"
        for bad in [{**good, "values": [True]}, {**good, "values": [3]}, {**good, "values": []},
                    {**good, "choice": {"flag": True}}, {**good, "fixed": "no"}, {**good, "text": "long"}]:
            with pytest.raises(ToolValidationError):
                runtime.call("test", bad)

    @pytest.mark.parametrize("schema", [{"$ref": "https://invalid.example/schema"}, {"type": ["string", "null"]},
        {"type": "string", "pattern": "(a+)+$"}, {"properties": {}}, {"type": "array", "items": True},
        {"type": "object", "additionalProperties": {}}, {"type": "object", "required": ["x", "x"]},
        {"type": "string", "minLength": -1}, {"type": "number", "minimum": 2, "maximum": 1},
        {"enum": []}])
    def test_rejects_unsupported_or_invalid_schema(self, schema) -> None:
        with pytest.raises(ToolValidationError):
            ToolRuntime(ToolSuite((ToolDefinition("bad", "bad", schema, (ToolResponse("ok"),)),)))

    def test_effects_are_in_memory_atomic_and_from_arguments(self) -> None:
        effects = (ToolEffect("set", "last", argument_path=("query",)),
                   ToolEffect("append", "history", argument_path=("query",)),
                   ToolEffect("increment", "count", 2))
        runtime = make_runtime(ToolResponse({"ok": True}, effects=effects), exhaustion="repeat_last")
        runtime.call("lookup", {"query": "one"}, correlation_id="one")
        runtime.call("lookup", {"query": "two"}, correlation_id="two")
        assert runtime.state == {"last": "two", "history": ["one", "two"], "count": 4}
        assert len([e for e in runtime.events if e["kind"] == "side_effect"]) == 6
        assert all(e["correlation_id"] in {"one", "two"} for e in runtime.events)
        broken = make_runtime(ToolResponse("bad", effects=(ToolEffect("set", "first", True),
            ToolEffect("append", "number", "x"))), initial_state={"number": 1})
        with pytest.raises(ToolValidationError):
            broken.call("lookup", {"query": "a"})
        assert broken.state == {"number": 1}
        assert not any(e["kind"] == "side_effect" for e in broken.events)

    def test_error_response_never_applies_effects(self) -> None:
        runtime = make_runtime(ToolResponse("refused", is_error=True, effects=(ToolEffect("set", "paid", True),)))
        response = runtime.call("lookup", {"query": "a"})
        assert response.is_error and runtime.state == {}
        assert [e["kind"] for e in runtime.events] == ["received", "failed"]

    def test_missing_argument_effect_path_does_not_mutate(self) -> None:
        runtime = make_runtime(ToolResponse("ok", effects=(ToolEffect("set", "value", argument_path=("missing",)),)))
        with pytest.raises(ToolValidationError):
            runtime.call("lookup", {"query": "ok"})
        assert runtime.state == {}

    def test_concurrent_calls_have_unique_linearized_slots_and_effects(self) -> None:
        response = ToolResponse("ok", effects=(ToolEffect("increment", "counter", 1),))
        runtime = make_runtime(response, exhaustion="repeat_last")
        with ThreadPoolExecutor(max_workers=8) as pool:
            answers = list(pool.map(lambda i: runtime.call("lookup", {"query": str(i)}, correlation_id=f"c-{i}"), range(40)))
        assert len(answers) == runtime.state["counter"] == 40
        received = [e for e in runtime.events if e["kind"] == "received"]
        assert [e["data"]["call_index"] for e in received] == list(range(1, 41))
        assert len({e["correlation_id"] for e in received}) == 40

    def test_gate_allows_second_response_to_finish_first_and_releases_explicitly(self) -> None:
        received = threading.Event()
        def sink(source, kind, data, *, correlation_id):
            if kind == "received" and data["call_index"] == 1:
                received.set()
        runtime = make_runtime(ToolResponse("first", gate="release"), ToolResponse("second"), event_sink=sink)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(runtime.call, "lookup", {"query": "a"})
            assert received.wait(1)
            with pytest.raises(ToolRuntimeError):
                runtime.snapshot()
            assert pool.submit(runtime.call, "lookup", {"query": "b"}).result(timeout=1).body == "second"
            runtime.release_gate("release")
            assert first.result(timeout=1).body == "first"
        completed = [e["data"]["call_index"] for e in runtime.events if e["kind"] == "completed"]
        assert completed == [2, 1]

    def test_timeout_has_no_effect_and_close_wakes_gate_waiter(self) -> None:
        runtime = make_runtime(ToolResponse("never", gate="hold", effects=(ToolEffect("set", "changed", True),)))
        with pytest.raises(ToolTimeoutError):
            runtime.call("lookup", {"query": "x"}, timeout=0.01)
        assert runtime.state == {} and runtime.healthy
        received = threading.Event()
        waiting = make_runtime(ToolResponse("never", gate="hold"), event_sink=lambda *a, **kw: received.set())
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(waiting.call, "lookup", {"query": "x"})
            assert received.wait(1)
            waiting.close()
            with pytest.raises(RuntimeClosedError):
                future.result(timeout=1)
        waiting.close()
        with pytest.raises(RuntimeClosedError):
            waiting.list_tools()

    def test_completion_gate_exposes_committed_effect_before_response(self) -> None:
        runtime = make_runtime(
            ToolResponse(
                "committed",
                completion_gate="return-response",
                effects=(ToolEffect("append", "delivered", "item-1"),),
            ),
            initial_state={"delivered": []},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(runtime.call, "lookup", {"query": "x"}, timeout=2)
            effect = runtime.wait_for_effect(
                "lookup",
                key="delivered",
                timeout=1,
            )

            assert effect["data"]["after"] == ["item-1"]
            assert runtime.state == {"delivered": ["item-1"]}
            assert not future.done()
            assert not any(event["kind"] == "completed" for event in runtime.events)

            runtime.release_gate("return-response")
            assert future.result(timeout=1).body == "committed"

    def test_completion_gate_timeout_does_not_rewind_committed_effect(self) -> None:
        runtime = make_runtime(
            ToolResponse(
                "committed",
                completion_gate="return-response",
                effects=(ToolEffect("set", "committed", True),),
            ),
            initial_state={"committed": False},
        )

        with pytest.raises(ToolTimeoutError, match="after effects"):
            runtime.call("lookup", {"query": "x"}, timeout=0.01)

        assert runtime.state == {"committed": True}
        assert [event["kind"] for event in runtime.events] == [
            "received",
            "side_effect",
            "failed",
        ]

    def test_delay_bounds_and_timeout(self) -> None:
        with pytest.raises(ToolValidationError):
            make_runtime(ToolResponse("slow", delay_seconds=2), max_delay_seconds=1)
        runtime = make_runtime(ToolResponse("slow", delay_seconds=0.1))
        with pytest.raises(ToolTimeoutError):
            runtime.call("lookup", {"query": "x"}, timeout=0.01)
        ready = make_runtime(ToolResponse("ready", delay_seconds=0.001))
        assert ready.call("lookup", {"query": "x"}).body == "ready"

    @pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, 301])
    def test_invalid_time_values(self, value) -> None:
        with pytest.raises(ToolValidationError):
            make_runtime(ToolResponse("bad", delay_seconds=value))

    def test_restore_rewinds_state_slots_and_gates_but_not_event_history(self) -> None:
        runtime = make_runtime(ToolResponse("first", gate="go", effects=(ToolEffect("increment", "count", 1),)), ToolResponse("second"))
        initial = runtime.snapshot()
        runtime.release_gate("go")
        runtime.call("lookup", {"query": "a"})
        runtime.restore(initial)
        assert runtime.state == {} and runtime.snapshot().call_counts == {"lookup": 0}
        assert runtime.snapshot().released_gates == () and len(runtime.events) == 3
        runtime.release_gate("go")
        assert runtime.call("lookup", {"query": "again"}).body == "first"
        assert runtime.state == {"count": 1} and len(runtime.events) == 6
        assert len({e["correlation_id"] for e in runtime.events}) == 2
        runtime.reset_gate("go")
        assert runtime.snapshot().released_gates == ()

    def test_restore_and_gate_reset_reject_inflight_calls(self) -> None:
        seen = threading.Event()
        runtime = make_runtime(ToolResponse("ok", gate="hold"), event_sink=lambda *a, **kw: seen.set())
        snapshot = runtime.snapshot()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(runtime.call, "lookup", {"query": "x"})
            assert seen.wait(1)
            with pytest.raises(ToolRuntimeError):
                runtime.restore(snapshot)
            with pytest.raises(ToolRuntimeError):
                runtime.reset_gate("hold")
            runtime.release_gate("hold")
            future.result(timeout=1)

    def test_snapshot_validation_and_no_aliasing(self) -> None:
        runtime = make_runtime(ToolResponse({"items": []}), initial_state={"list": []})
        snapshot = runtime.snapshot()
        snapshot.state["list"].append("changed")
        assert runtime.state == {"list": []}
        for bad in [replace(snapshot, suite_digest="different"), replace(snapshot, call_counts={"lookup": -1}),
                    replace(snapshot, released_gates=("unknown",)), replace(snapshot, state=[] )]:
            with pytest.raises(ToolValidationError):
                runtime.restore(bad)
        listed = runtime.list_tools()
        listed[0]["inputSchema"]["required"].clear()
        assert runtime.list_tools()[0]["inputSchema"]["required"] == ["query"]
        response = runtime.call("lookup", {"query": "x"})
        response.body["items"].append("changed")
        assert runtime.events[-1]["data"]["body"] == {"items": []}

    def test_sink_failure_fails_closed_before_effects(self) -> None:
        def broken(*args, **kwargs):
            raise OSError("simulated ledger outage")
        runtime = make_runtime(ToolResponse("ok", effects=(ToolEffect("set", "sent", True),)), event_sink=broken)
        with pytest.raises(RuntimeHealthError):
            runtime.call("lookup", {"query": "x"})
        assert not runtime.healthy and runtime.state == {}
        assert runtime.events[0]["kind"] == "received"
        with pytest.raises(RuntimeHealthError):
            runtime.call("lookup", {"query": "again"})

    def test_sink_failure_after_commit_does_not_claim_rollback(self) -> None:
        def fail_after_commit(source, kind, data, *, correlation_id):
            if kind == "side_effect":
                raise OSError("simulated failure")
        runtime = make_runtime(ToolResponse("ok", effects=(ToolEffect("set", "sent", True),)), event_sink=fail_after_commit)
        with pytest.raises(RuntimeHealthError):
            runtime.call("lookup", {"query": "x"})
        assert runtime.state == {"sent": True} and not runtime.healthy
        assert [e["kind"] for e in runtime.events] == ["received", "side_effect"]

    def test_sink_failure_wakes_other_inflight_calls(self) -> None:
        first_received = threading.Event()
        def fail_on_completed(source, kind, data, *, correlation_id):
            if kind == "received" and data["call_index"] == 1:
                first_received.set()
            if kind == "completed":
                raise OSError("simulated ledger failure")
        runtime = make_runtime(ToolResponse("wait", gate="hold"), ToolResponse("finish"), event_sink=fail_on_completed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            waiting = pool.submit(runtime.call, "lookup", {"query": "first"})
            assert first_received.wait(1)
            failing = pool.submit(runtime.call, "lookup", {"query": "second"})
            with pytest.raises(RuntimeHealthError):
                failing.result(timeout=1)
            with pytest.raises(RuntimeHealthError):
                waiting.result(timeout=1)
        assert not runtime.healthy

    def test_argument_paths_support_objects_and_arrays_without_attribute_access(self) -> None:
        response = ToolResponse("ok", effects=(ToolEffect("append", "items", argument_path=("rows", 0, "value")),))
        runtime = ToolRuntime(ToolSuite((ToolDefinition("copy", "copy", {"type": "object"}, (response,)),)))
        arguments = {"rows": [{"value": {"nested": [1]}}]}
        runtime.call("copy", arguments)
        arguments["rows"][0]["value"]["nested"].append(2)
        assert runtime.state == {"items": [{"nested": [1]}]}

    def test_restore_copies_input_and_restores_released_gate(self) -> None:
        runtime = make_runtime(ToolResponse("ok", gate="go"), exhaustion="repeat_last")
        runtime.release_gate("go")
        snapshot = runtime.snapshot()
        runtime.reset_gate("go")
        runtime.restore(snapshot)
        snapshot.state["external"] = True
        snapshot.call_counts["lookup"] = 99
        assert runtime.state == {} and runtime.snapshot().call_counts == {"lookup": 0}
        assert runtime.call("lookup", {"query": "x"}).body == "ok"

    def test_initial_state_and_suite_are_isolated_from_caller_mutation(self) -> None:
        schema = {"type": "object", "additionalProperties": False}
        body = {"data": [1]}
        state = {"events": []}
        runtime = ToolRuntime(ToolSuite((ToolDefinition("test", "test", schema, (ToolResponse(body),)),)), initial_state=state)
        schema["additionalProperties"] = True
        body["data"].append(2)
        state["events"].append("external")
        assert runtime.state == {"events": []}
        assert runtime.call("test", {}).body == {"data": [1]}
        assert runtime.list_tools()[0]["inputSchema"]["additionalProperties"] is False

    def test_unknown_tool_and_invalid_suite(self) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolValidationError):
            runtime.call("missing", {})
        assert runtime.events[-1]["kind"] == "failed"
        definition = ToolDefinition("duplicate", "d", {}, (ToolResponse("ok"),))
        with pytest.raises(ToolValidationError):
            ToolRuntime(ToolSuite((definition, definition)))
        with pytest.raises(ToolValidationError):
            ToolRuntime(ToolSuite(()))

    def test_wait_returns_early_received_event_as_deep_copy(self) -> None:
        runtime = make_runtime(ToolResponse("ok"), exhaustion="repeat_last")
        runtime.call("lookup", {"query": "first"}, correlation_id="first")
        runtime.call("lookup", {"query": "second"}, correlation_id="second")
        event = runtime.wait_for_call("lookup", count=2, timeout=1)
        assert event["kind"] == "received" and event["correlation_id"] == "second"
        event["data"]["arguments"]["query"] = "changed"
        assert runtime.wait_for_call("lookup", count=2)["data"]["arguments"]["query"] == "second"

    def test_wait_observes_late_receipt_before_gate_completion(self, monkeypatch) -> None:
        runtime = make_runtime(ToolResponse("ok", gate="release"))
        waiting = threading.Event()
        original_wait = runtime._condition.wait
        def observed_wait(timeout=None):
            waiting.set()
            return original_wait(timeout)
        monkeypatch.setattr(runtime._condition, "wait", observed_wait)
        with ThreadPoolExecutor(max_workers=2) as pool:
            observer = pool.submit(runtime.wait_for_call, "lookup", timeout=1)
            assert waiting.wait(1)
            call = pool.submit(runtime.call, "lookup", {"query": "late"}, timeout=2)
            try:
                event = observer.result(timeout=1)
                assert event["data"]["arguments"] == {"query": "late"}
                assert not call.done()
                assert not any(e["kind"] == "completed" for e in runtime.events)
            finally:
                runtime.release_gate("release")
            assert call.result(timeout=1).body == "ok"

    def test_wait_count_uses_retained_history_across_restore_and_failed_arguments(self) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        snapshot = runtime.snapshot()
        with pytest.raises(ToolValidationError):
            runtime.call("lookup", {}, correlation_id="invalid")
        assert runtime.wait_for_call("lookup")["correlation_id"] == "invalid"
        runtime.restore(snapshot)
        runtime.call("lookup", {"query": "valid"}, correlation_id="valid")
        event = runtime.wait_for_call("lookup", count=2)
        assert event["correlation_id"] == "valid" and event["data"]["call_index"] == 1

    def test_wait_times_out_when_target_receipt_is_missing(self) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolTimeoutError):
            runtime.wait_for_call("lookup", timeout=0.01)
        runtime.call("lookup", {"query": "one"})
        with pytest.raises(ToolTimeoutError):
            runtime.wait_for_call("lookup", count=2, timeout=0.01)

    @pytest.mark.parametrize("failure", ["close", "health"])
    def test_wait_wakes_and_fails_when_runtime_closes_or_sink_fails(self, monkeypatch, failure) -> None:
        def sink(*args, **kwargs):
            if failure == "health":
                raise OSError("synthetic ledger failure")
        runtime = make_runtime(ToolResponse("ok"), event_sink=sink)
        waiting = threading.Event()
        original_wait = runtime._condition.wait
        def observed_wait(timeout=None):
            waiting.set()
            return original_wait(timeout)
        monkeypatch.setattr(runtime._condition, "wait", observed_wait)
        expected = RuntimeClosedError if failure == "close" else RuntimeHealthError
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(runtime.wait_for_call, "lookup", timeout=2)
            assert waiting.wait(1)
            if failure == "close":
                runtime.close()
            else:
                with pytest.raises(RuntimeHealthError):
                    runtime.call("lookup", {"query": "fail"})
            with pytest.raises(expected):
                future.result(timeout=1)
        with pytest.raises(expected):
            runtime.wait_for_call("lookup")

    @pytest.mark.parametrize("count", [0, -1, True, 1.0, "1", None])
    def test_wait_rejects_invalid_count(self, count) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolValidationError):
            runtime.wait_for_call("lookup", count=count)

    @pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 301, "1", None, 10**1000])
    def test_wait_rejects_invalid_timeout(self, timeout) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolValidationError):
            runtime.wait_for_call("lookup", timeout=timeout)

    @pytest.mark.parametrize("name", ["", "missing", None, [], 1])
    def test_wait_rejects_invalid_tool_name(self, name) -> None:
        runtime = make_runtime(ToolResponse("ok"))
        with pytest.raises(ToolValidationError):
            runtime.wait_for_call(name)

    def test_public_wait_and_gate_work_in_parallel_runner_without_private_sink(self) -> None:
        runtime = make_runtime(ToolResponse("released", gate="ready"))
        def release_after_receipt(context):
            event = runtime.wait_for_call("lookup", timeout=1)
            assert event["kind"] == "received"
            runtime.release_gate("ready")
            return event["correlation_id"]
        with ScenarioRunner() as runner:
            result = runner.parallel({
                "call": lambda ctx: runtime.call("lookup", {"query": "demo"}, correlation_id="call", timeout=1),
                "release": release_after_receipt,
            }, timeout=2)
        assert result["call"].body == "released" and result["release"] == "call"
        runtime.close()
