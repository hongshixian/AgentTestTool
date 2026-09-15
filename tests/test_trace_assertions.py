"""Verify deterministic downstream assertions over reconstructed Agent traces."""

from __future__ import annotations

import pytest

from agent_models.evidence import EvidencePhase, EvidenceRecord, EvidenceStatus
from assertions.trace import (
    assert_model_context_contains,
    assert_reconstructed_trace_ready,
    assert_tool_lifecycle,
)


def test_ready_trace_supports_context_and_complete_tool_lifecycle() -> None:
    records = _records()

    assert_reconstructed_trace_ready(
        records, session_id="session-1", turn_id="turn-1"
    )
    assert_model_context_contains(
        records,
        "run the status tool",
        session_id="session-1",
        turn_id="turn-1",
    )
    assert_tool_lifecycle(
        records, "TRACE_STATUS", session_id="session-1", turn_id="turn-1"
    )


def test_single_turn_trace_can_be_selected_implicitly() -> None:
    records = _records()

    assert_reconstructed_trace_ready(records)
    assert_model_context_contains(records, "run the status tool")
    assert_tool_lifecycle(records, "TRACE_STATUS")


def test_unavailable_or_partial_trace_cannot_be_used_as_fact() -> None:
    unavailable = list(_records())
    unavailable[0] = EvidenceRecord(
        "reconstructed_agent_trace",
        "agent_trace_evidence",
        EvidencePhase.AFTER,
        unavailable[0].data,
        status=EvidenceStatus.UNVERIFIED,
    )

    with pytest.raises(AssertionError, match="不可用于事实断言"):
        assert_reconstructed_trace_ready(
            unavailable, session_id="session-1", turn_id="turn-1"
        )

    partial = list(_records())
    partial[0] = EvidenceRecord(
        "reconstructed_agent_trace",
        "agent_trace_evidence",
        EvidencePhase.AFTER,
        {**partial[0].data, "ready_state": "partial"},
    )
    with pytest.raises(AssertionError, match="不完整"):
        assert_reconstructed_trace_ready(
            partial, session_id="session-1", turn_id="turn-1"
        )


def test_tool_assertion_rejects_proposal_without_actual_execution() -> None:
    records = list(_records())
    trace = records[0].data
    tool_events = trace["sessions"][0]["turns"][0]["model_calls"][0]
    tool_events["tool_calls"] = tool_events["tool_calls"][:1]
    tool_events["tool_results"] = []

    with pytest.raises(AssertionError, match="完整且有序"):
        assert_tool_lifecycle(
            records, "TRACE_STATUS", session_id="session-1", turn_id="turn-1"
        )


def test_assertions_do_not_reuse_evidence_from_an_earlier_turn() -> None:
    records = list(_records())
    trace = records[0].data
    trace["sessions"][0]["turns"].append(
        {
            "turn_id": "turn-2",
            "ready_state": "ready",
            "model_calls": [
                {
                    "model_call_id": "call-2",
                    "messages": [
                        {
                            "phase": "request",
                            "visibility": "current",
                            "ready_state": "ready",
                            "content": "a different request",
                        }
                    ],
                    "tool_calls": [],
                    "tool_results": [],
                }
            ],
        }
    )

    with pytest.raises(AssertionError, match="预期文本"):
        assert_model_context_contains(
            records,
            "run the status tool",
            session_id="session-1",
            turn_id="turn-2",
        )
    with pytest.raises(AssertionError, match="指定工具"):
        assert_tool_lifecycle(
            records, "TRACE_STATUS", session_id="session-1", turn_id="turn-2"
        )
    with pytest.raises(AssertionError, match="turn_id"):
        assert_model_context_contains(records, "run the status tool")


def test_tool_lifecycle_ignores_replayed_history_results() -> None:
    records = list(_records())
    trace = records[0].data
    call = trace["sessions"][0]["turns"][0]["model_calls"][0]
    call["tool_results"][0]["ready_state"] = "replayed"

    with pytest.raises(AssertionError, match="完整且有序"):
        assert_tool_lifecycle(
            records, "TRACE_STATUS", session_id="session-1", turn_id="turn-1"
        )


def test_tool_lifecycle_selects_same_name_calls_by_exact_arguments() -> None:
    records = list(_records())
    call = records[0].data["sessions"][0]["turns"][0]["model_calls"][0]
    call["tool_calls"][0]["arguments"]["params"] = {"query": "first"}
    call["tool_calls"][1]["arguments"] = {"query": "first"}
    call["tool_calls"].extend(
        [
            {
                "tool_call_id": "tool-2",
                "name": "DeferExecuteTool",
                "arguments": {
                    "toolName": "mcp__ats_mock__TRACE_STATUS",
                    "params": {"query": "second"},
                },
                "stage": "proposed",
                "sequence": 5,
            },
            {
                "tool_call_id": "tool-2",
                "name": "mcp__ats_mock__TRACE_STATUS",
                "arguments": {"query": "second"},
                "stage": "received",
                "sequence": 6,
            },
        ]
    )
    call["tool_results"].extend(
        [
            {"tool_call_id": "tool-2", "stage": "completed", "sequence": 7},
            {"tool_call_id": "tool-2", "stage": "returned", "sequence": 8},
        ]
    )

    assert_tool_lifecycle(
        records,
        "TRACE_STATUS",
        expected_arguments={"query": "second"},
    )
    with pytest.raises(AssertionError, match="指定工具"):
        assert_tool_lifecycle(
            records,
            "TRACE_STATUS",
            expected_arguments={"query": "missing"},
        )


def _records() -> tuple[EvidenceRecord, EvidenceRecord]:
    trace = {
        "schema_version": "1.0",
        "run_id": "run-1",
        "product": "codebuddy",
        "ready_state": "ready",
        "collector_health": "healthy",
        "lost_event_count": 0,
        "sessions": [
            {
                "session_id": "session-1",
                "turns": [
                    {
                        "turn_id": "turn-1",
                        "model_calls": [
                            {
                                "model_call_id": "call-1",
                                "messages": [
                                    {
                                        "phase": "request",
                                        "visibility": "current",
                                        "ready_state": "ready",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "run the status tool",
                                            }
                                        ],
                                    }
                                ],
                                "tool_calls": [
                                    {
                                        "tool_call_id": "tool-1",
                                        "name": "DeferExecuteTool",
                                        "arguments": {
                                            "tool_name": "mcp__ats_mock__TRACE_STATUS"
                                        },
                                        "stage": "proposed",
                                        "sequence": 1,
                                    },
                                    {
                                        "tool_call_id": "tool-1",
                                        "name": "mcp__ats_mock__TRACE_STATUS",
                                        "stage": "received",
                                        "sequence": 2,
                                    },
                                ],
                                "tool_results": [
                                    {
                                        "tool_call_id": "tool-1",
                                        "stage": "completed",
                                        "sequence": 3,
                                    },
                                    {
                                        "tool_call_id": "tool-1",
                                        "stage": "returned",
                                        "sequence": 4,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    context = {
        "model_calls": [
            {
                "model_call_id": "call-1",
                "messages": [
                    {
                        "phase": "request",
                        "visibility": "current",
                        "content": [
                            {"type": "text", "text": "run the status tool"}
                        ],
                    }
                ],
            }
        ]
    }
    return (
        EvidenceRecord(
            "reconstructed_agent_trace",
            "agent_trace_evidence",
            EvidencePhase.AFTER,
            trace,
        ),
        EvidenceRecord(
            "observed_model_context",
            "agent_trace_evidence",
            EvidencePhase.AFTER,
            context,
        ),
    )
