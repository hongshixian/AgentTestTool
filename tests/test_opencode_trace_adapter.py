"""OpenCode public JSONL evidence must not masquerade as a complete model trace."""

from __future__ import annotations

import json

import pytest

from agent_models.evidence import (
    EvidenceAuthority,
    EvidencePhase,
    EvidenceRequest,
    EvidenceStatus,
    RequestContext,
)
from agent_models.opencode.trace_adapter import OpenCodeTraceAdapter


def _request(session_id: str | None = "ses-one") -> EvidenceRequest:
    return EvidenceRequest(
        "H071", "01", 1, EvidencePhase.AFTER,
        context=RequestContext("test-user", None, "run-1"), session_id=session_id,
    )


def _stream() -> str:
    events = (
        {"type": "step_start", "timestamp": 1000, "sessionID": "ses-one",
         "part": {"type": "step-start", "sessionID": "ses-one", "messageID": "msg-1"}},
        {"type": "tool_use", "timestamp": 2000, "sessionID": "ses-one",
         "part": {"type": "tool", "sessionID": "ses-one", "messageID": "msg-1",
                  "tool": "ats_mock_lookup", "callID": "call-1", "state": {
                      "status": "completed", "input": {"key": "secret-value"},
                      "output": "secret-value", "time": {"start": 1000, "end": 2000},
                  }}},
        {"type": "text", "timestamp": 2500, "sessionID": "ses-one",
         "part": {"type": "text", "sessionID": "ses-one", "text": "secret-value"}},
        {"type": "step_finish", "timestamp": 3000, "sessionID": "ses-one",
         "part": {"type": "step-finish", "sessionID": "ses-one", "reason": "stop"}},
    )
    return "\n".join(json.dumps(item) for item in events)


def test_public_jsonl_emits_partial_runtime_trace_not_complete_model_trace() -> None:
    records = OpenCodeTraceAdapter().capture(
        _request(), raw_events=_stream(), run_id="run-1",
        started_at_ms=1000, ended_at_ms=3000,
    )
    assert {record.evidence_id for record in records} == {
        "agent_runtime_events", "opencode_public_trace",
    }
    runtime, trace = records
    assert runtime.status is EvidenceStatus.AVAILABLE
    assert runtime.source.authority is EvidenceAuthority.PRODUCT_RUNTIME
    assert runtime.correlation.run_id == "run-1"
    assert runtime.correlation.session_ids == ("ses-one",)
    assert runtime.correlation.tool_use_ids == ("call-1",)
    assert [event["kind"] for event in runtime.data["events"]] == [
        "step_start", "tool_use", "text", "step_finish",
    ]
    turn = trace.data["sessions"][0]["turns"][0]
    assert trace.data["ready_state"] == "partial"
    assert turn["model_calls"] == []
    assert turn["runtime_effects"][0]["outcome"] == "completed"
    assert "secret-value" not in json.dumps([r.judge_payload() for r in records])
    assert trace.proves == ("Observed OpenCode CLI tool terminal states, when present",)


def test_redactor_applies_to_tool_input_output_and_text_before_return() -> None:
    def redact(value: object) -> object:
        if isinstance(value, str):
            return value.replace("secret-value", "[REDACTED]")
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value

    records = OpenCodeTraceAdapter().capture(
        _request(), raw_events=_stream(), run_id="run-1", redactor=redact,
    )
    events = records[0].data["events"]
    assert events[1]["input"] == {"key": "[REDACTED]"}
    assert events[1]["output"] == "[REDACTED]"
    assert events[2]["text"] == "[REDACTED]"
    assert "secret-value" not in json.dumps([r.judge_payload() for r in records])


@pytest.mark.parametrize("raw", [
    '{"type":"text","sessionID":"ses-one"}\nnot json',
    '{"type":"text","sessionID":"ses-two"}',
    '{"type":"text","sessionID":"ses-one","part":{"sessionID":"ses-two"}}',
    "[]", "", "x" * (2 * 1024 * 1024 + 1),
])
def test_invalid_or_foreign_event_stream_fails_closed(raw: str) -> None:
    records = OpenCodeTraceAdapter().capture(_request(), raw_events=raw, run_id="run-1")
    assert len(records) == 1
    assert records[0].status is EvidenceStatus.UNVERIFIED
    assert records[0].data == {"events": []}
    if len(raw) > 8:
        assert raw[:64] not in json.dumps(records[0].diagnostic_payload())


def test_multiple_sessions_or_out_of_window_event_fail_closed() -> None:
    events = _stream().splitlines()
    foreign = json.loads(events[-1])
    foreign["sessionID"] = "ses-two"
    foreign["part"]["sessionID"] = "ses-two"
    mixed = "\n".join((*events, json.dumps(foreign)))
    adapter = OpenCodeTraceAdapter()
    assert adapter.capture(_request(None), raw_events=mixed, run_id="run-1")[0].status is EvidenceStatus.UNVERIFIED
    assert adapter.capture(
        _request(), raw_events=_stream(), run_id="run-1",
        started_at_ms=1001, ended_at_ms=3000,
    )[0].status is EvidenceStatus.UNVERIFIED


def test_before_phase_and_run_mismatch_do_not_claim_evidence() -> None:
    request = EvidenceRequest("H071", "01", 1, EvidencePhase.BEFORE)
    assert OpenCodeTraceAdapter().capture(request, raw_events=_stream(), run_id="run-1") == ()
    with pytest.raises(ValueError, match="run_id"):
        OpenCodeTraceAdapter().capture(_request(), raw_events=_stream(), run_id="run-wrong")


def test_unknown_events_do_not_create_model_or_tool_claims() -> None:
    raw = json.dumps({"type": "opaque", "sessionID": "ses-one", "part": {"tool": "fake"}})
    records = OpenCodeTraceAdapter().capture(_request(), raw_events=raw, run_id="run-1")
    assert all(record.status is EvidenceStatus.MISSING for record in records)
    assert records[1].data["sessions"][0]["turns"][0]["model_calls"] == []


def test_bounded_content_drops_oversized_tool_result() -> None:
    event = {"type": "tool_use", "sessionID": "ses-one", "part": {
        "tool": "ats_mock_lookup", "callID": "call-1",
        "state": {"status": "error", "output": "X" * 5000},
    }}
    records = OpenCodeTraceAdapter().capture(
        _request(), raw_events=[event], run_id="run-1", redactor=lambda value: value,
    )
    assert "output" not in records[0].data["events"][0]
    assert records[1].data["sessions"][0]["turns"][0]["runtime_effects"][0]["outcome"] == "error"
