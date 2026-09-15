"""Verify CodeBuddy Trace evidence packaging and lifecycle integration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent_models.codebuddy.model import (
    CodeBuddyAgentModel,
    _TraceCollectorQuality,
    _TraceWindowStart,
    _trace_intervals_overlap,
)
from agent_models.codebuddy.trace_adapter import TraceTurnObservation
from agent_models.evidence import EvidencePhase, EvidenceRequest
from agent_models.environment.session import ControlledEnvironment
from agent_models.interaction import BackgroundTaskHandle, BackgroundTaskObservation
from evidence_collectors.base import (
    CollectionCheckpoint,
    CollectorHealth,
    CollectorHealthState,
    CollectorResult,
    CollectorStatus,
    EvidenceCursor,
    utc_now,
)
from evidence_collectors.manager import CollectionBatch
from evidence_collectors.trace import (
    AgentSession,
    AgentTrace,
    AgentTurn,
    ModelCall,
    ToolCallStage,
    TraceMessage,
    TracePhase,
    TraceReadyState,
    TraceToolCall,
)


class _Driver:
    is_dedicated_test_account = True

    def __init__(self) -> None:
        self.index = 0
        self.states: dict[str, str] = {}

    def start_background_task(self, _prompt, *, name, **_kwargs):
        self.index += 1
        self.states[f"task-{self.index}"] = "done"
        return BackgroundTaskHandle(
            task_id=f"task-{self.index}",
            name=name,
            session_id=f"session-{self.index}",
        )

    def observe_background_tasks(self):
        return tuple(
            BackgroundTaskObservation(
                task_id=f"task-{index}",
                name=f"task-{index}",
                kind="background",
                state=self.states[f"task-{index}"],
                session_id=f"session-{index}",
            )
            for index in range(1, self.index + 1)
        )

    def read_background_task_logs(self, task_id):
        return f"logs for {task_id}"

    def close(self, **_kwargs):
        return None


class _MockTool:
    extra_args = ()

    def capture(self, _request):
        return ()

    def close(self):
        return None


class _CollectorManager:
    def __init__(self, observations=(), *, health=None) -> None:
        self.sequence = 0
        self.windows = []
        self.closed = False
        self.observations = tuple(observations)
        self.health = health or CollectorHealth()

    def checkpoint(self, label):
        self.sequence += 1
        return CollectionCheckpoint(
            label,
            {"https_mitm": EvidenceCursor("https_mitm", str(self.sequence))},
        )

    def drain(self, _timeout):
        return CollectionBatch(
            {
                "https_mitm": CollectorResult(
                    "https_mitm",
                    CollectorStatus.MISSING,
                    CollectorHealth(),
                )
            }
        )

    def collect(self, window):
        self.windows.append(window.label)
        return CollectionBatch(
            {
                "https_mitm": CollectorResult(
                    "https_mitm",
                    (
                        CollectorStatus.AVAILABLE
                        if self.observations and self.health.healthy
                        else CollectorStatus.UNVERIFIED
                        if self.observations
                        else CollectorStatus.MISSING
                    ),
                    self.health,
                    observations=self.observations,
                )
            }
        )

    def close(self):
        self.closed = True


class _FailOnceCollectorManager(_CollectorManager):
    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def collect(self, window):
        if not self.failed:
            self.failed = True
            raise RuntimeError("temporary collection failure")
        return super().collect(window)


class _RecordingTraceAdapter:
    def __init__(self) -> None:
        self.calls = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return AgentTrace(
            run_id=kwargs["run_id"],
            product="codebuddy",
            sessions=(),
            ready_state=TraceReadyState.UNAVAILABLE,
            collector_health=kwargs["collector_health"],
            lost_event_count=kwargs["lost_event_count"],
            limitations=tuple(kwargs["limitations"]),
        )


def _model(tmp_path, *, collector_manager=None):
    environment = ControlledEnvironment(
        tmp_path / "workspace",
        evidence_directory=tmp_path / "evidence",
        run_id="trace-evidence-run",
    )
    return CodeBuddyAgentModel(
        workspace=environment.workspace.root,
        driver=_Driver(),
        evidence=SimpleNamespace(is_available=lambda: False),
        mock_tool=_MockTool(),
        local_state=SimpleNamespace(is_available=lambda: False),
        environment=environment,
        collector_manager=collector_manager,
        test_case_id="ATS-TRACE-EVIDENCE",
    )


def test_network_bodies_are_archived_in_bounded_hash_anchored_chunks(tmp_path):
    model = _model(tmp_path)
    window = _TraceWindowStart(
        "turn-1",
        "prompt",
        "session-1",
        CollectionCheckpoint("before", {}),
        utc_now().isoformat(),
    )
    large_body = "四" * 250_000

    references = model._archive_network_turn(
        window,
        (
            {
                "exchange_id": "exchange-1",
                "path": "/v2/chat/completions",
                "request_body": large_body,
                "response_body": large_body,
            },
        ),
    )

    body_references = [item for item in references if item["kind"] != "turn_manifest"]
    assert len(body_references) == 6
    assert all(int(item["bytes"]) < 1_048_576 for item in references)
    manifest_reference = next(
        item for item in references if item["kind"] == "turn_manifest"
    )
    manifest = json.loads(
        (model.environment.evidence_directory / str(manifest_reference["filename"])).read_text()
    )
    assert "request_body" not in manifest["exchanges"][0]
    assert len(manifest["exchanges"][0]["request_body_artifacts"]) == 3
    model.close()


def test_atif_trajectory_is_archived_beside_existing_trace_artifacts(tmp_path):
    model = _model(tmp_path)
    trace = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(
            AgentSession(
                "session-1",
                turns=(AgentTurn("turn-1", 0, "prompt"),),
            ),
        ),
    )

    model._archive_atif_trajectories(trace)

    payload = json.loads(
        (model.environment.evidence_directory / "trajectory.json").read_text()
    )
    assert payload["schema_version"] == "ATIF-v1.7"
    assert payload["session_id"] == "session-1"
    assert any(
        event["kind"] == "export_completed"
        for event in model.environment.ledger.events
    )
    model.close()


def test_atif_conversion_failure_does_not_change_trace_evidence_status(tmp_path):
    model = _model(tmp_path)
    trace = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(),
    )

    class _BrokenConverter:
        def convert(self, _trace):
            raise RuntimeError("unsupported mapping")

    model._atif_converter = _BrokenConverter()
    records = model._trace_records(
        EvidenceRequest("sample", "prompt", 1, EvidencePhase.AFTER),
        trace,
        turns=(),
        collector_errors=(),
        network_artifacts=(),
    )

    reconstructed = next(
        item for item in records if item.evidence_id == "reconstructed_agent_trace"
    )
    assert reconstructed.status.value == "available"
    assert any(
        event["kind"] == "export_failed"
        for event in model.environment.ledger.events
    )
    model.close()


def test_later_atif_snapshot_does_not_overwrite_or_reuse_stale_trajectory(tmp_path):
    model = _model(tmp_path)
    first = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(AgentSession("session-1"),),
    )
    second = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(
            AgentSession(
                "session-1",
                turns=(AgentTurn("turn-1", 0, "new prompt"),),
            ),
        ),
    )

    model._archive_atif_trajectories(first)
    model._archive_atif_trajectories(second)

    assert len(list(model.environment.evidence_directory.glob("trajectory*.json"))) == 2
    original = json.loads(
        (model.environment.evidence_directory / "trajectory.json").read_text()
    )
    assert original["steps"] == []
    model.close()


def test_trace_records_are_turn_scoped_and_claim_only_observed_tool_stages(tmp_path):
    model = _model(
        tmp_path,
        collector_manager=SimpleNamespace(close=lambda: None),
    )
    trace = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(
            AgentSession(
                "session-1",
                (
                    AgentTurn(
                        "turn-1",
                        0,
                        "prompt",
                        model_calls=(
                            ModelCall(
                                "call-1",
                                0,
                                messages=(
                                    TraceMessage(
                                        "message-1",
                                        "assistant",
                                        "done",
                                        0,
                                        TracePhase.RESPONSE,
                                    ),
                                ),
                                tool_calls=(
                                    TraceToolCall(
                                        "tool-1",
                                        "demo",
                                        {"value": 1},
                                        ToolCallStage.PROPOSED,
                                        1,
                                        TracePhase.RESPONSE,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    records = model._trace_records(
        EvidenceRequest("sample", "prompt", 1, EvidencePhase.AFTER),
        trace,
        turns=(),
        collector_errors=(),
        network_artifacts=(),
    )
    by_id = {record.evidence_id: record for record in records}
    output = by_id["observed_model_output"].data["model_calls"][0]
    tool_trace = by_id["observed_tool_trace"]

    assert output["session_id"] == "session-1"
    assert output["turn_id"] == "turn-1"
    assert output["tool_calls"][0]["stage"] == "proposed"
    assert "proposed" in tool_trace.proves[0]
    assert "received" not in tool_trace.proves[0]
    model.close()


def test_background_trace_windows_are_kept_per_task(tmp_path):
    manager = _CollectorManager()
    model = _model(tmp_path, collector_manager=manager)
    first = model.start_background_task("first", name="task-1", allow_tools=False)
    second = model.start_background_task("second", name="task-2", allow_tools=False)

    records = model.capture_evidence(
        EvidenceRequest(
            "sample",
            "prompt",
            1,
            EvidencePhase.AFTER,
            task_id=first.task_id,
        )
    )

    assert len(manager.windows) == 1
    assert first.task_id not in model._background_trace_windows
    assert second.task_id in model._background_trace_windows
    captured_turn = model._trace_turns[0]
    assert captured_turn.task_id == first.task_id
    assert [item.task_id for item in captured_turn.competing_turns] == [
        second.task_id
    ]
    reconstructed = next(
        record
        for record in records
        if record.evidence_id == "reconstructed_agent_trace"
    )
    assert reconstructed.correlation.task_ids == (first.task_id,)
    model.close()
    assert len(manager.windows) == 2
    assert manager.closed
    second_turn = model._trace_turns[1]
    assert second_turn.task_id == second.task_id
    assert [item.task_id for item in second_turn.competing_turns] == [
        first.task_id
    ]


def test_background_execution_without_network_capture_has_no_trace_window(tmp_path):
    model = _model(tmp_path)
    handle = model.start_background_task("first", name="task-1", allow_tools=False)

    records = model.capture_evidence(
        EvidenceRequest(
            "sample",
            "prompt",
            1,
            EvidencePhase.AFTER,
            task_id=handle.task_id,
        )
    )

    assert not model.capabilities.network_traffic_evidence
    assert "reconstructed_agent_trace" not in {
        record.evidence_id for record in records
    }
    model.close()


def test_running_background_task_is_not_finalized_as_complete_trace(tmp_path):
    manager = _CollectorManager()
    model = _model(tmp_path, collector_manager=manager)
    handle = model.start_background_task("first", name="task-1", allow_tools=False)
    model.driver.states[handle.task_id] = "working"

    model.capture_evidence(
        EvidenceRequest(
            "sample",
            "prompt",
            1,
            EvidencePhase.AFTER,
            task_id=handle.task_id,
        )
    )

    assert manager.windows == []
    assert handle.task_id in model._background_trace_windows
    model.driver.states[handle.task_id] = "done"
    model.close()


def test_trace_quality_is_scoped_to_the_selected_background_task(tmp_path):
    model = _model(tmp_path, collector_manager=SimpleNamespace(close=lambda: None))
    adapter = _RecordingTraceAdapter()
    model._trace_adapter = adapter
    first = TraceTurnObservation(
        "turn-1",
        "first",
        "session-1",
        (),
        task_id="task-1",
    )
    second = TraceTurnObservation(
        "turn-2",
        "second",
        "session-2",
        (),
        task_id="task-2",
    )
    model._trace_turns.extend((first, second))
    model._trace_quality_by_turn[first.turn_id] = _TraceCollectorQuality(
        health_state=CollectorHealthState.UNHEALTHY,
        lost_records=3,
        limitations=("first failed",),
        errors=("first error",),
        failed=True,
    )
    model._trace_quality_by_turn[second.turn_id] = _TraceCollectorQuality(
        limitations=("second limitation",),
    )

    model._capture_trace_evidence(
        EvidenceRequest(
            "sample",
            "prompt",
            1,
            EvidencePhase.AFTER,
            task_id="task-2",
        ),
        tool_records=(),
    )

    call = adapter.calls[-1]
    assert call["turns"] == (second,)
    assert call["collector_health"] == "healthy"
    assert call["lost_event_count"] == 0
    assert call["limitations"] == ("second limitation",)
    model.close()


def test_close_retries_unfinished_trace_window_before_closing_environment(tmp_path):
    manager = _FailOnceCollectorManager()
    model = _model(tmp_path, collector_manager=manager)
    handle = model.start_background_task("first", name="task-1", allow_tools=False)

    with pytest.raises(BaseExceptionGroup, match="Agent Model cleanup failed"):
        model.close()

    assert handle.task_id in model._background_trace_windows
    assert not model._trace_turns
    assert not manager.closed
    assert not model.environment._closed

    model.close()

    assert handle.task_id not in model._background_trace_windows
    assert len(model._trace_turns) == 1
    assert manager.closed
    assert model._closed


def test_artifact_save_failure_reuses_staged_collection_on_retry(
    tmp_path,
    monkeypatch,
) -> None:
    exchange = {
        "exchange_id": "exchange-1",
        "method": "POST",
        "path": "/v2/chat/completions",
        "request_body": '{"messages":[]}',
        "response_body": 'data: [DONE]\n\n',
        "request_complete": True,
        "response_complete": True,
        "request_body_truncated": False,
        "response_body_truncated": False,
        "error": None,
    }
    manager = _CollectorManager(
        (exchange,),
        health=CollectorHealth(
            CollectorHealthState.DEGRADED,
            "degraded window",
            2,
        ),
    )
    model = _model(tmp_path, collector_manager=manager)
    window = _TraceWindowStart(
        "turn-late-artifact",
        "prompt",
        "session-1",
        manager.checkpoint("before"),
        utc_now().isoformat(),
    )
    ledger = model.environment.ledger
    original_save = ledger.save_artifact
    save_calls = 0

    def fail_second_save(name, payload):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 2:
            original_save(name, payload)
            raise RuntimeError("temporary artifact failure")
        return original_save(name, payload)

    monkeypatch.setattr(ledger, "save_artifact", fail_second_save)

    with pytest.raises(RuntimeError, match="temporary artifact failure"):
        model._finish_trace_window(window)

    assert manager.windows == [window.turn_id]
    assert model._trace_turns == []
    assert window.turn_id not in model._trace_quality_by_turn
    assert model._collector_lost_records == 0
    assert window.turn_id not in model._finalized_trace_window_ids
    assert len(ledger._artifacts) == 2

    model._finish_trace_window(window)

    assert manager.windows == [window.turn_id]
    assert len(model._trace_turns) == 1
    assert model._collector_lost_records == 2
    assert len(model._network_artifacts) == 3
    assert len(ledger._artifacts) == 3
    assert len({item["filename"] for item in model._network_artifacts}) == 3
    model.close()


def test_turn_event_failure_does_not_duplicate_staged_turn_or_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    exchange = {
        "exchange_id": "exchange-1",
        "method": "POST",
        "path": "/v2/chat/completions",
        "request_body": '{"messages":[]}',
        "response_body": 'data: [DONE]\n\n',
        "request_complete": True,
        "response_complete": True,
        "request_body_truncated": False,
        "response_body_truncated": False,
        "error": None,
    }
    manager = _CollectorManager((exchange,))
    model = _model(tmp_path, collector_manager=manager)
    window = _TraceWindowStart(
        "turn-late-event",
        "prompt",
        "session-1",
        manager.checkpoint("before"),
        utc_now().isoformat(),
    )
    ledger = model.environment.ledger
    original_record = ledger.record
    failed = False

    def fail_turn_event(source, kind, data, correlation_id=None):
        nonlocal failed
        if source == "network_collector" and kind == "turn_captured" and not failed:
            failed = True
            original_record(source, kind, data, correlation_id)
            raise RuntimeError("temporary event failure")
        return original_record(source, kind, data, correlation_id)

    monkeypatch.setattr(ledger, "record", fail_turn_event)

    with pytest.raises(RuntimeError, match="temporary event failure"):
        model._finish_trace_window(window)

    artifact_names = tuple(ledger._artifacts)
    assert manager.windows == [window.turn_id]
    assert model._trace_turns == []
    assert window.turn_id not in model._trace_quality_by_turn

    model._finish_trace_window(window)

    assert manager.windows == [window.turn_id]
    assert len(model._trace_turns) == 1
    assert tuple(ledger._artifacts) == artifact_names
    assert len(model._network_artifacts) == len(artifact_names)
    captured_events = [
        event
        for event in ledger.events
        if event["source"] == "network_collector"
        and event["kind"] == "turn_captured"
        and event["correlation_id"] == window.turn_id
    ]
    assert len(captured_events) == 1
    model.close()


def test_naive_trace_timestamp_fails_closed_as_overlapping() -> None:
    assert _trace_intervals_overlap(
        "2026-09-15T08:00:00",
        "2026-09-15T08:00:10+00:00",
        "2026-09-15T08:00:20+00:00",
        "2026-09-15T08:00:30+00:00",
    )


def test_non_model_telemetry_failure_does_not_invalidate_complete_model_trace(
    tmp_path,
):
    model = _model(tmp_path, collector_manager=SimpleNamespace(close=lambda: None))
    result = CollectorResult(
        "https_mitm",
        CollectorStatus.ERROR,
        CollectorHealth(CollectorHealthState.UNHEALTHY, "incomplete exchange", 1),
        observations=(
            {
                "method": "POST",
                "path": "/v2/chat/completions",
                "request_complete": True,
                "response_complete": True,
                "request_body_truncated": False,
                "response_body_truncated": False,
                "error": None,
            },
            {
                "method": "POST",
                "path": "/v1/traces",
                "request_complete": True,
                "response_complete": False,
                "request_body_truncated": False,
                "response_body_truncated": False,
                "error": "SSLEOFError",
            },
        ),
        diagnostics={
            "retained_error_types": ["SSLEOFError"],
            "unattributed_error_count": 0,
            "dropped_error_count": 0,
            "resource_limits": [],
        },
    )

    assert not model._update_trace_collector_quality(result)
    assert model._collector_health_state is CollectorHealthState.HEALTHY
    assert any("非模型" in item for item in model._collector_limitations)
    model.close()


def test_model_exchange_failure_still_invalidates_trace(tmp_path):
    model = _model(tmp_path, collector_manager=SimpleNamespace(close=lambda: None))
    result = CollectorResult(
        "https_mitm",
        CollectorStatus.ERROR,
        CollectorHealth(CollectorHealthState.UNHEALTHY, "incomplete exchange", 1),
        observations=(
            {
                "method": "POST",
                "path": "/v2/chat/completions",
                "request_complete": True,
                "response_complete": False,
                "request_body_truncated": False,
                "response_body_truncated": False,
                "error": "SSLEOFError",
            },
        ),
        diagnostics={
            "retained_error_types": ["SSLEOFError"],
            "unattributed_error_count": 0,
            "dropped_error_count": 0,
            "resource_limits": [],
        },
    )

    assert model._update_trace_collector_quality(result)
    assert model._collector_health_state is CollectorHealthState.UNHEALTHY
    model.close()


def test_unscoped_collector_error_fails_closed(tmp_path):
    model = _model(tmp_path, collector_manager=SimpleNamespace(close=lambda: None))
    result = CollectorResult(
        "https_mitm",
        CollectorStatus.ERROR,
        CollectorHealth(CollectorHealthState.UNHEALTHY, "unscoped error", 1),
        observations=(
            {
                "method": "POST",
                "path": "/v1/traces",
                "request_complete": True,
                "response_complete": False,
                "request_body_truncated": False,
                "response_body_truncated": False,
                "error": "SSLEOFError",
            },
        ),
    )

    assert model._update_trace_collector_quality(result)
    assert model._collector_health_state is CollectorHealthState.UNHEALTHY
    model.close()


def test_network_error_and_ready_model_trace_are_reported_separately(tmp_path):
    model = _model(tmp_path, collector_manager=SimpleNamespace(close=lambda: None))
    trace = AgentTrace(
        run_id=model.environment.run_id,
        product="codebuddy",
        sessions=(
            AgentSession(
                "session-1",
                (
                    AgentTurn(
                        "turn-1",
                        0,
                        "prompt",
                        model_calls=(ModelCall("call-1", 0),),
                    ),
                ),
            ),
        ),
    )
    turns = (
        TraceTurnObservation(
            "turn-1",
            "prompt",
            "session-1",
            (
                {
                    "method": "POST",
                    "path": "/v2/chat/completions",
                    "request_complete": True,
                    "response_complete": True,
                    "request_body_truncated": False,
                    "response_body_truncated": False,
                    "error": None,
                },
                {
                    "method": "POST",
                    "path": "/v1/traces",
                    "request_complete": True,
                    "response_complete": False,
                    "request_body_truncated": False,
                    "response_body_truncated": False,
                    "error": "SSLEOFError",
                },
            ),
        ),
    )

    records = model._trace_records(
        EvidenceRequest("sample", "prompt", 1, EvidencePhase.AFTER),
        trace,
        turns=turns,
        collector_errors=(),
        network_artifacts=(),
    )
    by_id = {record.evidence_id: record for record in records}

    assert by_id["network_exchange_trace"].status.value == "error"
    assert by_id["reconstructed_agent_trace"].status.value == "available"
    assert by_id["collector_quality_report"].data["network_failure_count"] == 1
    model.close()
