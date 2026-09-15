"""Verify portable ATIF conversion from the internal Agent Trace."""

from __future__ import annotations

import pytest

from evidence_collectors.atif import ATIF_SCHEMA_VERSION, AtifConverter
from evidence_collectors.trace import (
    AgentSession,
    AgentTrace,
    AgentTurn,
    ModelCall,
    ToolCallStage,
    TraceMessage,
    TracePhase,
    TraceReadyState,
    TraceReasoning,
    TraceToolCall,
    TraceToolResult,
    TraceVisibility,
)


def _call(identifier: str, sequence: int, *, tool: bool = False) -> ModelCall:
    kwargs = {}
    if tool:
        kwargs = {
            "tool_calls": (
                TraceToolCall(
                    "call-1", "read_file", {"path": "README.md"},
                    ToolCallStage.PROPOSED, 2, TracePhase.RESPONSE,
                ),
                TraceToolCall(
                    "call-1", "read_file", {"path": "README.md"},
                    ToolCallStage.DISPATCHED, 3, TracePhase.RUNTIME,
                    source="stream-json",
                ),
            ),
            "tool_results": (
                TraceToolResult(
                    "call-1", "contents", ToolCallStage.COMPLETED, 4,
                    TracePhase.RUNTIME, source="mock-mcp",
                ),
                TraceToolResult(
                    "call-1", "contents", ToolCallStage.RETURNED, 5,
                    TracePhase.REQUEST, visibility=TraceVisibility.HISTORY,
                ),
            ),
        }
    return ModelCall(
        identifier,
        sequence,
        model="model-a",
        completed_at=f"2026-01-01T00:00:0{sequence}+00:00",
        messages=(
            TraceMessage(
                f"message-{identifier}", "assistant", f"answer-{identifier}",
                1, TracePhase.RESPONSE,
            ),
        ),
        reasoning=(
            TraceReasoning(f"reason-{identifier}", "explicit summary", 1),
        ),
        **kwargs,
    )


def _trace(*, sessions: int = 1) -> AgentTrace:
    return AgentTrace(
        run_id="run-1",
        product="codebuddy",
        test_case_id="ATS-1",
        sessions=tuple(
            AgentSession(
                f"session-{index}",
                turns=(
                    AgentTurn(
                        f"turn-{index}", 0, "hello",
                        model_calls=(_call("one", 0, tool=True), _call("two", 1)),
                        ready_state=TraceReadyState.PARTIAL,
                        limitations=("partial response",),
                    ),
                ),
                limitations=("session limitation",),
            )
            for index in range(sessions)
        ),
        ready_state=TraceReadyState.PARTIAL,
        collector_health="degraded",
        lost_event_count=2,
        limitations=("trace limitation",),
    )


def test_converts_turn_and_each_model_call_to_ordered_atif_steps():
    trajectory = AtifConverter().convert(_trace())[0]
    payload = trajectory.to_payload()

    assert payload["schema_version"] == ATIF_SCHEMA_VERSION
    assert [step["step_id"] for step in payload["steps"]] == [1, 2, 3]
    assert [step["source"] for step in payload["steps"]] == ["user", "agent", "agent"]
    assert payload["steps"][1]["message"] == "answer-one"
    assert payload["steps"][1]["reasoning_content"] == "explicit summary"
    assert payload["steps"][1]["llm_call_count"] == 1


def test_preserves_tool_correlation_lifecycle_and_quality_extensions():
    payload = AtifConverter().convert(_trace())[0].to_payload()
    agent_step = payload["steps"][1]

    assert agent_step["tool_calls"][0]["tool_call_id"] == "call-1"
    assert agent_step["observation"]["results"][0]["source_call_id"] == "call-1"
    lifecycle = agent_step["extra"]["agent_test_tool"]["tool_lifecycle"]["call-1"]
    assert [item["stage"] for item in lifecycle] == [
        "proposed", "dispatched", "completed", "returned"
    ]
    extension = payload["extra"]["agent_test_tool"]
    assert extension["trace_ready_state"] == "partial"
    assert extension["lost_event_count"] == 2
    assert extension["session_limitations"] == ["session limitation"]


def test_multiple_sessions_produce_multiple_trajectories():
    trajectories = AtifConverter().convert(_trace(sessions=2))

    assert [item.session_id for item in trajectories] == ["session-0", "session-1"]


def test_payload_is_detached_from_model_data():
    trajectory = AtifConverter().convert(_trace())[0]
    payload = trajectory.to_payload()
    payload["steps"][1]["tool_calls"][0]["arguments"]["path"] = "changed"

    assert trajectory.to_payload()["steps"][1]["tool_calls"][0]["arguments"]["path"] == "README.md"


def test_trace_rejects_ambiguous_out_of_order_tool_lifecycle():
    with pytest.raises(ValueError, match="lifecycle stages must be ordered"):
        AgentTurn(
            "turn", 0, "prompt",
            model_calls=(
                ModelCall(
                    "call", 0,
                    tool_calls=(
                        TraceToolCall(
                            "tool", "name", {}, ToolCallStage.DISPATCHED, 2,
                            TracePhase.RUNTIME,
                        ),
                        TraceToolCall(
                            "tool", "name", {}, ToolCallStage.PROPOSED, 3,
                            TracePhase.RESPONSE,
                        ),
                    ),
                ),
            ),
        )
