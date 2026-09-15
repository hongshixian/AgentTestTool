"""Verify the product-neutral Agent trace intermediate representation."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from evidence_collectors import (
    AgentSession,
    AgentTrace,
    AgentTurn,
    ModelCall,
    ToolCallStage,
    TraceMessage,
    TracePhase,
    TraceReadyState,
    TraceReasoning,
    TraceRuntimeEffect,
    TraceToolCall,
    TraceToolResult,
    TraceVisibility,
)


def test_complete_trace_is_immutable_and_json_safe() -> None:
    trace = _trace()

    payload = trace.to_payload()
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)

    assert '"run_id": "run-1"' in encoded
    assert payload["sessions"][0]["turns"][0]["model_calls"][0][
        "tool_calls"
    ][0]["stage"] == "proposed"
    assert payload["sessions"][0]["turns"][0]["runtime_effects"][0][
        "phase"
    ] == "runtime"
    with pytest.raises(FrozenInstanceError):
        trace.run_id = "different"  # type: ignore[misc]
    message = trace.sessions[0].turns[0].model_calls[0].messages[0]
    with pytest.raises(TypeError):
        message.content["nested"] = "different"  # type: ignore[index]


def test_payload_is_detached_from_immutable_trace_data() -> None:
    trace = _trace()

    payload = trace.to_payload()
    message_content = payload["sessions"][0]["turns"][0]["model_calls"][0][
        "messages"
    ][0]["content"]
    message_content["nested"][0] = "changed"

    fresh = trace.to_payload()
    assert fresh["sessions"][0]["turns"][0]["model_calls"][0]["messages"][0][
        "content"
    ] == {"nested": ["value"]}


def test_trace_supports_visibility_phase_and_readiness_states() -> None:
    messages = (
        TraceMessage(
            "current",
            "user",
            "now",
            0,
            TracePhase.REQUEST,
            TraceVisibility.CURRENT,
            TraceReadyState.READY,
        ),
        TraceMessage(
            "history",
            "assistant",
            "earlier",
            1,
            TracePhase.REQUEST,
            TraceVisibility.HISTORY,
            TraceReadyState.REPLAYED,
        ),
        TraceMessage(
            "background",
            "user",
            "make title",
            2,
            TracePhase.REQUEST,
            TraceVisibility.BACKGROUND,
            TraceReadyState.PARTIAL,
        ),
    )
    call = ModelCall(
        "call-1",
        0,
        ready_state=TraceReadyState.UNAVAILABLE,
        messages=messages,
        limitations=("response body was not decrypted",),
    )

    payload = call.to_payload()

    assert [item["visibility"] for item in payload["messages"]] == [
        "current",
        "history",
        "background",
    ]
    assert [item["ready_state"] for item in payload["messages"]] == [
        "ready",
        "replayed",
        "partial",
    ]
    assert payload["ready_state"] == "unavailable"


@pytest.mark.parametrize(
    ("stage", "phase"),
    [
        (ToolCallStage.PROPOSED, TracePhase.RESPONSE),
        (ToolCallStage.DISPATCHED, TracePhase.RUNTIME),
        (ToolCallStage.RECEIVED, TracePhase.RUNTIME),
        (ToolCallStage.COMPLETED, TracePhase.RUNTIME),
        (ToolCallStage.RETURNED, TracePhase.REQUEST),
    ],
)
def test_tool_call_supports_every_lifecycle_stage(
    stage: ToolCallStage, phase: TracePhase
) -> None:
    item = TraceToolCall("tool-1", "read_file", {}, stage, 0, phase)

    assert item.to_payload()["stage"] == stage.value


def test_basic_validation_rejects_invalid_identifiers_and_payloads() -> None:
    with pytest.raises(ValueError, match="message_id must be nonempty"):
        TraceMessage(" ", "user", "hello", 0, TracePhase.REQUEST)
    with pytest.raises(ValueError, match="non-finite"):
        TraceMessage("message-1", "user", {"score": float("nan")}, 0, TracePhase.REQUEST)
    with pytest.raises(ValueError, match="non-JSON"):
        TraceMessage("message-1", "user", {"bad": object()}, 0, TracePhase.REQUEST)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="completed or returned"):
        TraceToolResult(
            "tool-1", {}, ToolCallStage.PROPOSED, 0, TracePhase.RESPONSE
        )
    with pytest.raises(ValueError, match="runtime phase"):
        TraceRuntimeEffect(
            "effect-1", "file", "write", 0, phase=TracePhase.RESPONSE
        )


def test_hierarchy_rejects_duplicate_ids_and_regressing_tool_stages() -> None:
    message = TraceMessage("message-1", "user", "hello", 0, TracePhase.REQUEST)
    with pytest.raises(ValueError, match="message identifiers must be unique"):
        ModelCall("call-1", 0, messages=(message, message))

    returned = TraceToolCall(
        "tool-1",
        "read_file",
        {},
        ToolCallStage.RETURNED,
        2,
        TracePhase.REQUEST,
    )
    completed = TraceToolCall(
        "tool-1",
        "read_file",
        {},
        ToolCallStage.COMPLETED,
        3,
        TracePhase.RUNTIME,
    )
    call = ModelCall("call-1", 0, tool_calls=(returned, completed))
    with pytest.raises(ValueError, match="lifecycle stages must be ordered"):
        AgentTurn("turn-1", 0, "hello", model_calls=(call,))


def _trace() -> AgentTrace:
    messages = (
        TraceMessage(
            "message-1",
            "user",
            {"nested": ["value"]},
            0,
            TracePhase.REQUEST,
            observed_at="2026-09-15T08:00:00Z",
        ),
        TraceMessage(
            "message-2",
            "assistant",
            "I will inspect the file.",
            1,
            TracePhase.RESPONSE,
        ),
    )
    reasoning = (
        TraceReasoning(
            "reasoning-1",
            {"summary": "Need to read the file"},
            2,
            limitations=("provider exposed only a summary",),
        ),
    )
    calls = (
        TraceToolCall(
            "tool-1",
            "read_file",
            {"path": "README.md"},
            ToolCallStage.PROPOSED,
            3,
            TracePhase.RESPONSE,
        ),
        TraceToolCall(
            "tool-1",
            "read_file",
            {"path": "README.md"},
            ToolCallStage.RECEIVED,
            4,
            TracePhase.RUNTIME,
            source="mock_mcp",
        ),
    )
    results = (
        TraceToolResult(
            "tool-1",
            {"text": "project readme"},
            ToolCallStage.COMPLETED,
            5,
            TracePhase.RUNTIME,
            source="mock_mcp",
        ),
        TraceToolResult(
            "tool-1",
            {"text": "project readme"},
            ToolCallStage.RETURNED,
            6,
            TracePhase.REQUEST,
        ),
    )
    model_call = ModelCall(
        "model-call-1",
        0,
        request_id="request-1",
        provider="openai-compatible",
        endpoint="https://example.invalid/v1/responses",
        model="fixture-model",
        messages=messages,
        reasoning=reasoning,
        tool_calls=calls,
        tool_results=results,
    )
    effect = TraceRuntimeEffect(
        "effect-1",
        "file",
        "read",
        7,
        {"path": "README.md", "bytes": 128},
        target="README.md",
        outcome="success",
        tool_call_id="tool-1",
    )
    turn = AgentTurn(
        "turn-1",
        0,
        "Read README.md",
        model_calls=(model_call,),
        runtime_effects=(effect,),
    )
    session = AgentSession("session-1", (turn,))
    return AgentTrace(
        "run-1",
        "fixture",
        (session,),
        test_case_id="ATS-TEST-01",
    )
