"""Offline guards against promoting uncorrelated IIIS packets to complete Trace."""

from __future__ import annotations

import json
import pytest

from agent_models.evidence import EvidencePhase, EvidenceRequest, EvidenceStatus, RequestContext
from agent_models.opencode.network_trace import OpenCodeNetworkTrace


PROMPT = "Read status"
HOST = "router.ai.iiis.co"


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        "H021", "01", 1, EvidencePhase.AFTER,
        context=RequestContext("test", None, "ses-run"), session_id="ses-one",
    )


def _exchange(index: int = 1, *, response: str | None = None) -> dict:
    response = response if response is not None else (
        "data: " + json.dumps({
            "id": f"chatcmpl-{index}", "choices": [{
                "index": 0, "finish_reason": "stop",
                "delta": {"content": "secret reply"},
            }],
        }) + "\n\ndata: [DONE]\n\n"
    )
    return {
        "exchange_id": f"proxy-id-{index}", "sequence": index,
        "started_at": "2026-09-23T08:00:01Z", "completed_at": "2026-09-23T08:00:02Z",
        "scheme": "https", "host": HOST, "port": 9443,
        "method": "POST", "path": "/v1/chat/completions",
        "intercepted": True,
        "request_headers": {
            "x-session-id": "ses-one", "x-turn-id": "turn-one",
            "x-ats-oc-agent": "build",
        },
        "response_headers": {"x-litellm-call-id": f"req-{index}", "content-type": "text/event-stream"},
        "request_body": json.dumps({
            "model": "infi/deepseek-v4.1-flash", "messages": [
                {"role": "system", "content": "secret system"},
                {"role": "user", "content": PROMPT},
            ],
        }),
        "response_body": response, "response_status": 200,
        "request_complete": True, "response_complete": True,
        "request_body_truncated": False, "response_body_truncated": False,
        "error": None,
    }


def _capture(*exchanges: dict, **kw: object):
    arguments = {
        "exchanges": exchanges, "run_id": "ses-run", "prompt": PROMPT,
        "session_id": "ses-one", "turn_id": "turn-one",
        "window_start": "2026-09-23T08:00:00Z",
        "window_end": "2026-09-23T08:00:03Z",
        "provider_host": HOST, "collector_healthy": True,
        "redactor": lambda value: _redact(value),
    }
    arguments.update(kw)
    return OpenCodeNetworkTrace().capture(_request(), **arguments)


def _redact(value):
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return value.replace("secret", "[REDACTED]")
    return value


def test_complete_explicitly_attributed_wire_requests_support_trace() -> None:
    records = _capture(_exchange())
    assert {record.evidence_id for record in records} == {
        "network_exchange_trace", "reconstructed_agent_trace",
        "observed_model_context", "observed_model_output", "observed_tool_trace",
    }
    assert all(record.status is EvidenceStatus.AVAILABLE for record in records[:-1])
    assert records[-1].status is EvidenceStatus.MISSING
    assert "secret" not in json.dumps([record.judge_payload() for record in records])
    assert "request_body" not in records[0].data["exchanges"][0]
    trace = records[1].data
    assert trace["ready_state"] == "ready"
    call = trace["sessions"][0]["turns"][0]["model_calls"][0]
    assert call["request_id"] == "req-1"
    assert call["messages"][0]["content"] == "[REDACTED] system"
    assert call["messages"][2]["content"] == "[REDACTED] reply"
    assert records[1].correlation.turn_ids == ("turn-one",)
    assert "evaluator-owned" in " ".join(records[1].limitations)
    assert "IIIS LiteLLM proxy" in " ".join(records[1].limitations)


@pytest.mark.parametrize("mutate", [
    lambda item: item["request_headers"].clear(),
    lambda item: item["request_headers"].pop("x-turn-id"),
    lambda item: item["response_headers"].pop("x-litellm-call-id"),
    lambda item: item.update({"request_body_truncated": True}),
    lambda item: item.update({"response_body_truncated": True}),
    lambda item: item.update({"intercepted": False}),
    lambda item: item.update({"response_body": "data: garbage\n\n"}),
    lambda item: item.update({"response_status": 401}),
    lambda item: item.update({"response_complete": False}),
    lambda item: item.update({"request_body": "{"}),
    lambda item: item.update({"started_at": "2026-09-23T07:59:58Z"}),
])
def test_missing_provenance_or_bad_framing_is_not_available(mutate) -> None:
    exchange = _exchange()
    mutate(exchange)
    records = _capture(exchange)
    assert records[0].status is EvidenceStatus.AVAILABLE
    assert all(record.status is EvidenceStatus.UNVERIFIED for record in records[1:])
    assert all(record.data == {} for record in records[1:])


def test_opaque_proxy_id_does_not_replace_provider_request_id() -> None:
    exchange = _exchange()
    exchange["response_headers"] = {"content-type": "text/event-stream"}
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_legacy_request_id_does_not_replace_litellm_proxy_id() -> None:
    exchange = _exchange()
    exchange["response_headers"].pop("x-litellm-call-id")
    exchange["response_headers"]["x-request-id"] = "req-legacy"
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_body_session_or_turn_id_cannot_replace_native_request_headers() -> None:
    for missing in ("x-session-id", "x-turn-id"):
        exchange = _exchange()
        exchange["request_headers"].pop(missing)
        body = json.loads(exchange["request_body"])
        body["session_id"] = "ses-one"
        body["turn_id"] = "turn-one"
        exchange["request_body"] = json.dumps(body)
        assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_conflicting_wire_session_ids_fail_closed() -> None:
    exchange = _exchange()
    body = json.loads(exchange["request_body"])
    body["session_id"] = "ses-other"
    exchange["request_body"] = json.dumps(body)
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_duplicate_provider_request_ids_fail_closed() -> None:
    second = _exchange(2)
    second["response_headers"]["x-litellm-call-id"] = "req-1"
    assert _capture(_exchange(), second)[1].status is EvidenceStatus.UNVERIFIED


@pytest.mark.parametrize("field,value", [
    ("x-session-id", "ses-other"), ("x-turn-id", "turn-other"),
])
def test_mixed_scoped_model_exchanges_fail_closed(field: str, value: str) -> None:
    background = _exchange(2)
    background["request_headers"][field] = value
    assert _capture(_exchange(), background)[1].status is EvidenceStatus.UNVERIFIED


def test_case_insensitive_duplicate_wire_header_fails_closed() -> None:
    exchange = _exchange()
    exchange["request_headers"]["X-Turn-Id"] = "turn-other"
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_other_host_model_background_inside_turn_fails_closed() -> None:
    background = _exchange(2)
    background["host"] = "another-provider.invalid"
    assert _capture(_exchange(), background)[1].status is EvidenceStatus.UNVERIFIED


def test_nonstream_json_without_done_does_not_claim_complete_response() -> None:
    exchange = _exchange()
    exchange["response_headers"]["content-type"] = "application/json"
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_missing_wire_ids_like_standard_opencode_iiis_do_not_claim_trace() -> None:
    exchange = _exchange()
    exchange["request_headers"] = {"content-type": "application/json"}
    result = _capture(exchange)
    assert result[0].status is EvidenceStatus.AVAILABLE
    assert result[1].status is EvidenceStatus.UNVERIFIED
    assert not result[1].available


@pytest.mark.parametrize("overrides", [
    {"competing_turns": True}, {"collector_healthy": False}, {"redactor": None},
])
def test_competing_turn_or_unhealthy_collection_fail_closed(overrides) -> None:
    records = _capture(_exchange(), **overrides)
    assert records[1].status is EvidenceStatus.UNVERIFIED


def test_unintercepted_provider_tunnel_blocks_full_trace() -> None:
    tunneled = _exchange(2)
    tunneled.update({
        "method": "CONNECT", "scheme": "connect", "path": HOST,
        "intercepted": False, "request_body": "", "response_body": "",
    })
    records = _capture(_exchange(), tunneled)
    assert records[1].status is EvidenceStatus.UNVERIFIED


def test_second_model_call_without_current_prompt_is_background_not_trace() -> None:
    exchange = _exchange(2)
    data = json.loads(exchange["request_body"])
    data["messages"][-1]["content"] = "Summarize this conversation"
    exchange["request_body"] = json.dumps(data)
    records = _capture(_exchange(1), exchange)
    assert records[1].status is EvidenceStatus.UNVERIFIED


def test_malformed_sse_and_no_done_cannot_claim_complete_response() -> None:
    event = json.dumps({
        "id": "response-1", "choices": [{"index": 0, "delta": {"content": "hello"},
                                           "finish_reason": "stop"}],
    })
    response = f"data: {event}\n\n"
    exchange = _exchange(response=response)
    exchange["response_headers"]["content-type"] = "text/event-stream"
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_valid_sse_tool_proposal_and_followup_tool_result() -> None:
    proposed = json.dumps({
        "id": "resp-1", "choices": [{"index": 0,
            "delta": {"tool_calls": [{"index": 0, "id": "tool-1",
                "function": {"name": "lookup", "arguments": '{"q":"status"}'}}]},
            "finish_reason": "tool_calls"}],
    })
    first = _exchange(1, response=f"data: {proposed}\n\ndata: [DONE]\n\n")
    first["response_headers"]["content-type"] = "text/event-stream"
    second = _exchange(2)
    body = json.loads(second["request_body"])
    body["messages"].extend([
        {"role": "assistant", "content": None, "tool_calls": [{"id": "tool-1"}]},
        {"role": "tool", "content": "secret state", "tool_call_id": "tool-1"},
    ])
    second["request_body"] = json.dumps(body)
    records = _capture(first, second)
    assert records[1].status is EvidenceStatus.AVAILABLE
    assert records[-1].status is EvidenceStatus.AVAILABLE
    turn = records[1].data["sessions"][0]["turns"][0]
    assert turn["model_calls"][0]["tool_calls"][0]["stage"] == "proposed"
    assert turn["model_calls"][1]["tool_results"][0]["stage"] == "returned"
    assert "secret state" not in json.dumps([record.judge_payload() for record in records])


def test_no_complete_model_exchange_has_no_factual_model_trace() -> None:
    records = _capture()
    assert records[0].status is EvidenceStatus.UNVERIFIED
    assert all(record.status is EvidenceStatus.MISSING for record in records[1:])


def _title_exchange(index: int = 2) -> dict:
    exchange = _exchange(index)
    exchange["request_headers"]["x-ats-oc-agent"] = "title"
    return exchange


def test_incomplete_title_response_does_not_contaminate_complete_primary_trace() -> None:
    title = _title_exchange()
    title.update({
        "response_complete": False, "response_body_truncated": True,
        "response_body": "data: incomplete", "response_status": None,
        "completed_at": None,
    })
    title["response_headers"] = {}
    records = _capture(_exchange(), title)
    assert records[0].status is EvidenceStatus.AVAILABLE
    assert len(records[0].data["exchanges"]) == 2
    assert records[1].status is EvidenceStatus.AVAILABLE
    calls = records[1].data["sessions"][0]["turns"][0]["model_calls"]
    assert [call["request_id"] for call in calls] == ["req-1"]
    assert records[1].correlation.request_ids == ("req-1",)


@pytest.mark.parametrize("agent", [None, "unknown", "compaction", "", "Build"])
def test_missing_or_unsupported_background_agent_rejects_complete_trace(agent: str | None) -> None:
    background = _title_exchange()
    if agent is None:
        background["request_headers"].pop("x-ats-oc-agent")
    else:
        background["request_headers"]["x-ats-oc-agent"] = agent
    assert _capture(_exchange(), background)[1].status is EvidenceStatus.UNVERIFIED


def test_primary_model_request_without_agent_classifier_fails_closed() -> None:
    main = _exchange()
    main["request_headers"].pop("x-ats-oc-agent")
    assert _capture(main)[1].status is EvidenceStatus.UNVERIFIED


def test_duplicate_agent_classifier_headers_fail_closed() -> None:
    title = _title_exchange()
    title["request_headers"]["X-Ats-Oc-Agent"] = "title"
    assert _capture(_exchange(), title)[1].status is EvidenceStatus.UNVERIFIED


def test_only_title_background_is_not_a_primary_model_trace() -> None:
    assert _capture(_title_exchange())[1].status is EvidenceStatus.UNVERIFIED


@pytest.mark.parametrize("field,value", [
    ("response_complete", False),
    ("response_body_truncated", True),
    ("response_status", 500),
])
def test_primary_response_must_still_be_complete(field: str, value: object) -> None:
    main = _exchange()
    main[field] = value
    assert _capture(main, _title_exchange())[1].status is EvidenceStatus.UNVERIFIED


def test_title_with_another_session_fails_even_if_response_incomplete() -> None:
    title = _title_exchange()
    title["request_headers"]["x-session-id"] = "another-session"
    title["response_complete"] = False
    assert _capture(_exchange(), title)[1].status is EvidenceStatus.UNVERIFIED


def test_title_with_incomplete_request_fails_closed() -> None:
    title = _title_exchange()
    title["request_complete"] = False
    assert _capture(_exchange(), title)[1].status is EvidenceStatus.UNVERIFIED


def _clean_title_error() -> tuple[dict, dict]:
    title = _title_exchange()
    title.update({
        "response_complete": False,
        "response_body_truncated": True,
        "error": "SSLEOFError: title stream closed when CLI exited",
        "response_body": "data: partial",
    })
    return title, {
        "retained_error_types": ["SSLEOFError"],
        "unattributed_error_count": 0,
        "dropped_error_count": 0,
        "resource_limits": [],
    }


def test_clean_title_only_collector_degradation_preserves_primary_trace() -> None:
    title, diagnostics = _clean_title_error()
    records = _capture(
        _exchange(), title, collector_healthy=False,
        collector_diagnostics=diagnostics,
    )
    assert records[0].status is EvidenceStatus.UNVERIFIED
    assert len(records[0].data["exchanges"]) == 2
    assert "overall HTTPS collector window is unhealthy" in " ".join(records[0].limitations)
    assert records[1].status is EvidenceStatus.AVAILABLE
    trace = records[1].data
    assert trace["collector_health"] == "title_response_degraded"
    assert [call["request_id"] for call in trace["sessions"][0]["turns"][0]["model_calls"]] == ["req-1"]
    assert "overall HTTPS collector window is unhealthy" in " ".join(records[1].limitations)


def test_degraded_window_rejects_additional_unrelated_error() -> None:
    title, diagnostics = _clean_title_error()
    unrelated = _exchange(3)
    unrelated["host"] = "other-host.invalid"
    unrelated["response_complete"] = False
    unrelated["error"] = "SSLEOFError: another endpoint closed"
    diagnostics["retained_error_types"] = ["SSLEOFError", "SSLEOFError"]
    assert _capture(_exchange(), title, unrelated, collector_healthy=False,
                    collector_diagnostics=diagnostics)[1].status is EvidenceStatus.UNVERIFIED


def test_degraded_window_rejects_incomplete_primary_call() -> None:
    title, diagnostics = _clean_title_error()
    main = _exchange()
    main["response_body_truncated"] = True
    assert _capture(main, title, collector_healthy=False,
                    collector_diagnostics=diagnostics)[1].status is EvidenceStatus.UNVERIFIED


@pytest.mark.parametrize("field,value", [
    ("dropped_error_count", 1),
    ("unattributed_error_count", 1),
    ("resource_limits", ["body_budget"]),
    ("retained_error_types", ["TimeoutError"]),
])
def test_degraded_window_rejects_bad_or_missing_quality_diagnostics(field: str, value: object) -> None:
    title, diagnostics = _clean_title_error()
    diagnostics[field] = value
    assert _capture(_exchange(), title, collector_healthy=False,
                    collector_diagnostics=diagnostics)[1].status is EvidenceStatus.UNVERIFIED
    diagnostics.pop(field)
    assert _capture(_exchange(), title, collector_healthy=False,
                    collector_diagnostics=diagnostics)[1].status is EvidenceStatus.UNVERIFIED


def test_user_prompt_with_transport_whitespace_is_still_correlated() -> None:
    exchange = _exchange()
    payload = json.loads(exchange["request_body"])
    payload["messages"][-1]["content"] = "\n" + PROMPT + "\n"
    exchange["request_body"] = json.dumps(payload)
    assert _capture(exchange)[1].status is EvidenceStatus.AVAILABLE
    payload["messages"][-1]["content"] = PROMPT + " and an unrelated instruction"
    exchange["request_body"] = json.dumps(payload)
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED


def test_opencode_json_string_wrapped_user_prompt_is_correlated_only_if_exact() -> None:
    exchange = _exchange()
    payload = json.loads(exchange["request_body"])
    payload["messages"][-1]["content"] = json.dumps(PROMPT)
    exchange["request_body"] = json.dumps(payload)
    assert _capture(exchange)[1].status is EvidenceStatus.AVAILABLE
    payload["messages"][-1]["content"] = json.dumps(PROMPT + " other request")
    exchange["request_body"] = json.dumps(payload)
    assert _capture(exchange)[1].status is EvidenceStatus.UNVERIFIED
