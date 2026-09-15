"""Verify CodeBuddy network, stream, and Mock MCP trace reconstruction."""

from __future__ import annotations

import json

from agent_models.codebuddy.trace_adapter import (
    CodeBuddyTraceAdapter,
    TraceTurnIdentity,
    TraceTurnObservation,
)
from agent_models.codebuddy.model import CodeBuddyAgentModel
from agent_models.evidence import EvidenceCorrelation, EvidencePhase, EvidenceRecord
from agent_models.interaction import AgentEvent, AgentEventType
from evidence_collectors import ToolCallStage, TraceReadyState, TraceVisibility


def _exchange(
    sequence: int,
    request: dict,
    response_lines: list[dict],
    *,
    complete: bool = True,
) -> dict:
    response = "\n\n".join(
        f"data: {json.dumps(item, ensure_ascii=False)}" for item in response_lines
    )
    if complete:
        response += "\n\ndata: [DONE]\n\n"
    return {
        "exchange_id": f"exchange-{sequence}",
        "sequence": sequence,
        "started_at": f"2026-09-15T08:00:0{sequence}Z",
        "completed_at": f"2026-09-15T08:00:0{sequence + 1}Z",
        "scheme": "https",
        "host": "copilot.tencent.com",
        "port": 443,
        "method": "POST",
        "path": "/v2/chat/completions",
        "request_headers": {"content-type": "application/json"},
        "request_body": json.dumps(request, ensure_ascii=False),
        "response_status": 200,
        "response_headers": {"x-request-id": f"request-{sequence}"},
        "response_body": response,
        "request_complete": True,
        "response_complete": complete,
        "error": None,
    }


def test_reconstructs_complete_tool_lifecycle_across_model_calls() -> None:
    first = _exchange(
        1,
        {
            "model": "fixture-model",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "old question"},
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": "Read status"},
            ],
        },
        [
            {
                "id": "response-1",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "status",
                                        "arguments": '{"scope":',
                                    },
                                }
                            ]
                        }
                    }
                ],
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '"local"}'},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ],
    )
    second = _exchange(
        2,
        {
            "model": "fixture-model",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "old question"},
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": "Read status"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "type": "function",
                            "function": {
                                "name": "status",
                                "arguments": '{"scope":"local"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "tool-1",
                    "content": '{"ready":true}',
                },
            ],
        },
        [
            {
                "id": "response-2",
                "choices": [{"delta": {"content": "Ready"}}],
            },
            {
                "choices": [
                    {"delta": {"content": "."}, "finish_reason": "stop"}
                ]
            },
        ],
    )
    event = AgentEvent(
        4,
        AgentEventType.TOOL_CALL,
        "2026-09-15T08:00:02Z",
        2.0,
        session_id="session-1",
        turn_id="turn-1",
        data={"id": "tool-1", "name": "status"},
    )
    mock_record = EvidenceRecord(
        "mock_tool_io",
        "runtime_evidence",
        EvidencePhase.AFTER,
        {
            "calls": [
                {
                    "tool_name": "status",
                    "arguments": {"scope": "local"},
                    "result": {
                        "content": [{"type": "text", "text": '{"ready":true}'}],
                        "structuredContent": {"ready": True},
                        "isError": False,
                    },
                }
            ]
        },
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        test_case_id="ATS-TEST-01",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "Read status",
                "session-1",
                (first, second),
                stream_events=(event,),
            ),
        ),
        tool_records=(mock_record,),
    )

    assert trace.ready_state is TraceReadyState.READY
    turn = trace.sessions[0].turns[0]
    assert len(turn.model_calls) == 2
    first_call, second_call = turn.model_calls
    assert [item.visibility for item in first_call.messages[:4]] == [
        TraceVisibility.HISTORY,
        TraceVisibility.HISTORY,
        TraceVisibility.HISTORY,
        TraceVisibility.CURRENT,
    ]
    assert [item.stage for item in first_call.tool_calls] == [
        ToolCallStage.PROPOSED,
        ToolCallStage.DISPATCHED,
        ToolCallStage.RECEIVED,
    ]
    assert first_call.tool_calls[0].arguments == {"scope": "local"}
    assert first_call.tool_results[0].stage is ToolCallStage.COMPLETED
    assert second_call.tool_results[0].stage is ToolCallStage.RETURNED
    assert second_call.messages[-1].content == "Ready."


def test_incomplete_model_response_marks_trace_partial() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [{"choices": [{"delta": {"content": "Hel"}}]}],
        complete=False,
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    assert trace.sessions[0].turns[0].model_calls[0].ready_state is TraceReadyState.PARTIAL
    assert any(
        "完整结束边界" in item
        for item in trace.sessions[0].turns[0].limitations
    )


def test_truncated_request_cannot_produce_ready_trace() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [{"choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}]}],
    )
    exchange["request_body_truncated"] = True

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    assert any(
        "采集上限" in item
        for item in trace.sessions[0].turns[0].limitations
    )


def test_non_model_traffic_does_not_become_an_agent_model_call() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [{"choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}]}],
    )
    exchange["path"] = "/v1/traces"

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    assert trace.sessions[0].turns[0].ready_state is TraceReadyState.UNAVAILABLE
    assert trace.sessions[0].turns[0].model_calls == ()


def test_explicit_reasoning_is_limited_and_not_described_as_hidden_cot() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_content": "Provider-visible summary",
                            "content": "Hi",
                        },
                        "finish_reason": "stop",
                    }
                ]
            }
        ],
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    item = trace.sessions[0].turns[0].model_calls[0].reasoning[0]
    assert item.content == "Provider-visible summary"
    assert "不代表隐藏思维链" in item.limitations[0]


def test_streamed_reasoning_deltas_are_coalesced() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [
            {"choices": [{"delta": {"reasoning_content": "part-"}}]},
            {
                "choices": [
                    {
                        "delta": {"reasoning_content": "two", "content": "Hi"},
                        "finish_reason": "stop",
                    }
                ]
            },
        ],
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    reasoning = trace.sessions[0].turns[0].model_calls[0].reasoning
    assert len(reasoning) == 1
    assert reasoning[0].content == "part-two"


def test_deferred_codebuddy_wrapper_links_to_actual_mock_mcp_target() -> None:
    first = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Call status"}]},
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "wrapper-call-1",
                                    "function": {
                                        "name": "DeferExecuteTool",
                                        "arguments": json.dumps(
                                            {
                                                "toolName": "mcp__ats_mock__TRACE_STATUS",
                                                "params": {"query": "probe"},
                                            }
                                        ),
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ],
    )
    second = _exchange(
        2,
        {
            "messages": [
                {"role": "user", "content": "Call status"},
                {
                    "role": "tool",
                    "tool_call_id": "wrapper-call-1",
                    "content": '{"trace_probe":"ok"}',
                },
            ]
        },
        [
            {
                "choices": [
                    {"delta": {"content": "done"}, "finish_reason": "stop"}
                ]
            }
        ],
    )
    record = EvidenceRecord(
        "mock_tool_io",
        "runtime_evidence",
        EvidencePhase.AFTER,
        {
            "calls": [
                {
                    "tool_name": "TRACE_STATUS",
                    "arguments": {"query": "probe"},
                    "result": {"structuredContent": {"trace_probe": "ok"}, "isError": False},
                }
            ]
        },
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1", "Call status", "session-1", (first, second)
            ),
        ),
        tool_records=(record,),
    )

    assert trace.ready_state is TraceReadyState.READY
    first_call = trace.sessions[0].turns[0].model_calls[0]
    assert [item.stage for item in first_call.tool_calls] == [
        ToolCallStage.PROPOSED,
        ToolCallStage.RECEIVED,
    ]
    assert first_call.tool_calls[0].name == "DeferExecuteTool"
    assert first_call.tool_calls[1].name == "mcp__ats_mock__TRACE_STATUS"
    assert first_call.tool_results[0].stage is ToolCallStage.COMPLETED


def test_known_deferred_arguments_never_fall_back_to_name_only_matching() -> None:
    exchange = _deferred_exchange(1, "turn-tool", query="expected")
    record = _mock_record(
        [
            {
                "tool_name": "TRACE_STATUS",
                "arguments": {"query": "different"},
                "result": {"structuredContent": {"trace_probe": "wrong"}},
            }
        ]
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1", "turn-tool", "session-1", (exchange,)
            ),
        ),
        tool_records=(record,),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    call = trace.sessions[0].turns[0].model_calls[0]
    assert [item.stage for item in call.tool_calls] == [ToolCallStage.PROPOSED]
    assert any("参数" in item for item in call.limitations)


def test_ambiguous_mock_calls_degrade_trace_instead_of_guessing() -> None:
    exchange = _deferred_exchange(1, "turn-tool", query="probe")
    duplicate = {
        "tool_name": "TRACE_STATUS",
        "arguments": {"query": "probe"},
        "result": {"structuredContent": {"trace_probe": "ok"}},
    }

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1", "turn-tool", "session-1", (exchange,)
            ),
        ),
        tool_records=(_mock_record([duplicate, duplicate]),),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    call = trace.sessions[0].turns[0].model_calls[0]
    assert all(item.stage is not ToolCallStage.RECEIVED for item in call.tool_calls)
    assert any("无法唯一关联" in item for item in call.limitations)


def test_overlapping_turn_does_not_claim_uncorrelated_mock_execution() -> None:
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "turn-tool",
                "session-1",
                (_deferred_exchange(1, "turn-tool", query="probe"),),
                task_id="task-1",
                competing_turns=(
                    TraceTurnIdentity(
                        "turn-2", "other prompt", "session-2", "task-2"
                    ),
                ),
            ),
        ),
        tool_records=(
            _mock_record(
                [
                    {
                        "tool_name": "TRACE_STATUS",
                        "arguments": {"query": "probe"},
                        "result": {"structuredContent": {"owner": "task-2"}},
                    }
                ]
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    call = trace.sessions[0].turns[0].model_calls[0]
    assert [item.stage for item in call.tool_calls] == [ToolCallStage.PROPOSED]
    assert call.tool_results == ()
    assert any("缺少可验证" in item for item in call.limitations)


def test_overlapping_turn_accepts_task_correlated_mock_execution() -> None:
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "turn-tool",
                "session-1",
                (_deferred_exchange(1, "turn-tool", query="probe"),),
                task_id="task-1",
                competing_turns=(
                    TraceTurnIdentity(
                        "turn-2", "other prompt", "session-2", "task-2"
                    ),
                ),
            ),
        ),
        tool_records=(
            _mock_record(
                [
                    {
                        "tool_name": "TRACE_STATUS",
                        "arguments": {"query": "probe"},
                        "result": {"structuredContent": {"owner": "task-1"}},
                    }
                ],
                correlation=EvidenceCorrelation(task_ids=("task-1",)),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.READY
    call = trace.sessions[0].turns[0].model_calls[0]
    assert [item.stage for item in call.tool_calls] == [
        ToolCallStage.PROPOSED,
        ToolCallStage.RECEIVED,
    ]
    assert [item.stage for item in call.tool_results] == [ToolCallStage.COMPLETED]


def test_shared_session_correlation_does_not_disambiguate_competing_turns() -> None:
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "turn-tool",
                "shared-session",
                (_deferred_exchange(1, "turn-tool", query="probe"),),
                task_id="task-1",
                competing_turns=(
                    TraceTurnIdentity(
                        "turn-2", "other prompt", "shared-session", "task-2"
                    ),
                ),
            ),
        ),
        tool_records=(
            _mock_record(
                [
                    {
                        "tool_name": "TRACE_STATUS",
                        "arguments": {"query": "probe"},
                        "result": {"structuredContent": {"owner": "unknown"}},
                    }
                ],
                correlation=EvidenceCorrelation(
                    session_ids=("shared-session",)
                ),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    call = trace.sessions[0].turns[0].model_calls[0]
    assert all(
        item.stage is not ToolCallStage.RECEIVED for item in call.tool_calls
    )


def test_background_title_and_summary_requests_are_not_added_to_business_turn() -> None:
    business = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Perform business action"}]},
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )
    title = _exchange(
        2,
        {
            "messages": [
                {"role": "user", "content": "Perform business action"},
                {"role": "assistant", "content": "done"},
                {"role": "user", "content": "Generate a short title"},
            ]
        },
        [{"choices": [{"delta": {"content": "A title"}, "finish_reason": "stop"}]}],
    )
    summary = _exchange(
        3,
        {
            "messages": [
                {"role": "user", "content": "Perform business action"},
                {"role": "assistant", "content": "done"},
                {"role": "user", "content": "Summarize this session"},
            ]
        },
        [{"choices": [{"delta": {"content": "A summary"}, "finish_reason": "stop"}]}],
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "Perform business action",
                "session-1",
                (business, title, summary),
            ),
        ),
    )

    turn = trace.sessions[0].turns[0]
    assert trace.ready_state is TraceReadyState.READY
    assert len(turn.model_calls) == 1
    assert any("已排除 2 个" in item for item in turn.limitations)


def test_unidentified_tool_continuation_fails_closed_in_single_window() -> None:
    proposed = _deferred_exchange(1, "Run status", query="probe")
    continuation = _exchange(
        2,
        {
            "messages": [
                {
                    "role": "tool",
                    "tool_call_id": "wrapper-1",
                    "content": '{"status":"ok"}',
                }
            ]
        },
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "Run status",
                "session-1",
                (proposed, continuation),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    turn = trace.sessions[0].turns[0]
    assert len(turn.model_calls) == 1
    assert any("无法可靠归属" in item for item in turn.limitations)


def test_explicit_metadata_header_is_safely_excluded() -> None:
    business = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Perform action"}]},
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )
    metadata = _exchange(
        2,
        {"messages": [{"role": "system", "content": "build metadata"}]},
        [{"choices": [{"delta": {"content": "meta"}, "finish_reason": "stop"}]}],
    )
    metadata["request_headers"]["x-agent-purpose"] = "session_metadata"

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "Perform action",
                "session-1",
                (business, metadata),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.READY
    turn = trace.sessions[0].turns[0]
    assert len(turn.model_calls) == 1
    assert any("已排除 1 个" in item for item in turn.limitations)


def test_overlapping_identical_prompts_use_exact_session_id() -> None:
    first = _exchange(
        1,
        {"messages": [{"role": "user", "content": "same prompt"}]},
        [{"choices": [{"delta": {"content": "first"}, "finish_reason": "stop"}]}],
    )
    second = _exchange(
        2,
        {"messages": [{"role": "user", "content": "same prompt"}]},
        [{"choices": [{"delta": {"content": "second"}, "finish_reason": "stop"}]}],
    )
    first["request_headers"]["x-conversation-id"] = "session-1"
    second["request_headers"]["x-conversation-id"] = "session-2"
    turns = (
        TraceTurnObservation(
            "turn-1",
            "same prompt",
            "session-1",
            (first, second),
            task_id="task-1",
            competing_turns=(
                TraceTurnIdentity("turn-2", "same prompt", "session-2", "task-2"),
            ),
        ),
        TraceTurnObservation(
            "turn-2",
            "same prompt",
            "session-2",
            (first, second),
            task_id="task-2",
            competing_turns=(
                TraceTurnIdentity("turn-1", "same prompt", "session-1", "task-1"),
            ),
        ),
    )

    trace = CodeBuddyTraceAdapter().build(run_id="run-1", turns=turns)

    assert trace.ready_state is TraceReadyState.READY
    calls = {
        session.session_id: session.turns[0].model_calls
        for session in trace.sessions
    }
    assert [call.request_id for call in calls["session-1"]] == ["request-1"]
    assert [call.request_id for call in calls["session-2"]] == ["request-2"]


def test_overlapping_same_session_prefers_exact_task_id() -> None:
    exchange = _exchange(
        1,
        {
            "taskId": "task-1",
            "messages": [{"role": "user", "content": "same prompt"}],
        },
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "same prompt",
                "shared-session",
                (exchange,),
                task_id="task-1",
                competing_turns=(
                    TraceTurnIdentity(
                        "turn-2", "same prompt", "shared-session", "task-2"
                    ),
                ),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.READY
    assert len(trace.sessions[0].turns[0].model_calls) == 1


def test_overlapping_contained_prompts_are_not_cross_assigned() -> None:
    short = _exchange(
        1,
        {"messages": [{"role": "user", "content": "scan"}]},
        [{"choices": [{"delta": {"content": "short"}, "finish_reason": "stop"}]}],
    )
    long = _exchange(
        2,
        {"messages": [{"role": "user", "content": "scan workspace"}]},
        [{"choices": [{"delta": {"content": "long"}, "finish_reason": "stop"}]}],
    )
    turns = (
        TraceTurnObservation(
            "turn-1",
            "scan",
            "session-1",
            (short, long),
            task_id="task-1",
            competing_turns=(
                TraceTurnIdentity(
                    "turn-2", "scan workspace", "session-2", "task-2"
                ),
            ),
        ),
        TraceTurnObservation(
            "turn-2",
            "scan workspace",
            "session-2",
            (short, long),
            task_id="task-2",
            competing_turns=(
                TraceTurnIdentity("turn-1", "scan", "session-1", "task-1"),
            ),
        ),
    )

    trace = CodeBuddyTraceAdapter().build(run_id="run-1", turns=turns)

    assert trace.ready_state is TraceReadyState.READY
    calls = {
        session.session_id: session.turns[0].model_calls
        for session in trace.sessions
    }
    assert [call.request_id for call in calls["session-1"]] == ["request-1"]
    assert [call.request_id for call in calls["session-2"]] == ["request-2"]


def test_overlapping_identical_prompts_without_ids_fail_closed() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "same prompt"}]},
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1",
                "same prompt",
                "session-1",
                (exchange,),
                task_id="task-1",
                competing_turns=(
                    TraceTurnIdentity(
                        "turn-2", "same prompt", "session-2", "task-2"
                    ),
                ),
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    turn = trace.sessions[0].turns[0]
    assert turn.model_calls == ()
    assert any("无法可靠归属" in item for item in turn.limitations)


def test_malformed_sse_data_marks_trace_partial_even_with_done_marker() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Hello"}]},
        [{"choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}]}],
    )
    exchange["response_body"] = (
        'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        "data: {not-json}\n\n"
        "data: [DONE]\n\n"
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation("turn-1", "Hello", "session-1", (exchange,)),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    assert any(
        "无法解析" in item for item in trace.sessions[0].turns[0].limitations
    )


def test_repeated_tool_result_is_marked_replayed() -> None:
    first = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Run tool"}]},
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "tool-1",
                                    "function": {"name": "ToolSearch", "arguments": "{}"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ],
    )
    messages = [
        {"role": "user", "content": "Run tool"},
        {"role": "tool", "tool_call_id": "tool-1", "content": "found"},
    ]
    second = _exchange(
        2,
        {"messages": messages},
        [{"choices": [{"delta": {"content": "working"}, "finish_reason": "stop"}]}],
    )
    third = _exchange(
        3,
        {"messages": messages},
        [{"choices": [{"delta": {"content": "done"}, "finish_reason": "stop"}]}],
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1", "Run tool", "session-1", (first, second, third)
            ),
        ),
    )

    results = [
        result
        for call in trace.sessions[0].turns[0].model_calls
        for result in call.tool_results
    ]
    assert [item.ready_state for item in results] == [
        TraceReadyState.READY,
        TraceReadyState.REPLAYED,
    ]


def test_same_name_stream_events_are_consumed_by_exact_id() -> None:
    exchange = _exchange(
        1,
        {"messages": [{"role": "user", "content": "Run both"}]},
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "id": "tool-1", "function": {"name": "ToolSearch", "arguments": "{}"}},
                                {"index": 1, "id": "tool-2", "function": {"name": "ToolSearch", "arguments": "{}"}},
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ],
    )
    events = (
        AgentEvent(1, AgentEventType.TOOL_CALL, "second", 1.0, data={"id": "tool-2", "name": "ToolSearch"}),
        AgentEvent(2, AgentEventType.TOOL_CALL, "first", 2.0, data={"id": "tool-1", "name": "ToolSearch"}),
    )

    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(TraceTurnObservation("turn-1", "Run both", "session-1", (exchange,), stream_events=events),),
    )

    dispatched = [
        item
        for item in trace.sessions[0].turns[0].model_calls[0].tool_calls
        if item.stage is ToolCallStage.DISPATCHED
    ]
    assert [(item.tool_call_id, item.observed_at) for item in dispatched] == [
        ("tool-1", "first"),
        ("tool-2", "second"),
    ]


def test_identical_mock_proposals_across_turns_are_not_globally_guessed() -> None:
    trace = CodeBuddyTraceAdapter().build(
        run_id="run-1",
        turns=(
            TraceTurnObservation(
                "turn-1", "first prompt", "session-1", (_deferred_exchange(1, "first prompt", query="probe"),)
            ),
            TraceTurnObservation(
                "turn-2", "second prompt", "session-1", (_deferred_exchange(2, "second prompt", query="probe"),)
            ),
        ),
        tool_records=(
            _mock_record(
                [
                    {"tool_name": "TRACE_STATUS", "arguments": {"query": "probe"}, "result": {"structuredContent": {"turn": 1}}},
                    {"tool_name": "TRACE_STATUS", "arguments": {"query": "probe"}, "result": {"structuredContent": {"turn": 2}}},
                ]
            ),
        ),
    )

    assert trace.ready_state is TraceReadyState.PARTIAL
    for turn in trace.sessions[0].turns:
        assert all(
            item.stage is not ToolCallStage.RECEIVED
            for item in turn.model_calls[0].tool_calls
        )
        assert any("跨多个回合" in item for item in turn.limitations)


def _deferred_exchange(sequence: int, prompt: str, *, query: str) -> dict:
    return _exchange(
        sequence,
        {"messages": [{"role": "user", "content": prompt}]},
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": f"wrapper-{sequence}",
                                    "function": {
                                        "name": "DeferExecuteTool",
                                        "arguments": json.dumps(
                                            {
                                                "toolName": "mcp__ats_mock__TRACE_STATUS",
                                                "params": {"query": query},
                                            }
                                        ),
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ],
    )


def _mock_record(
    calls: list[dict],
    *,
    correlation: EvidenceCorrelation = EvidenceCorrelation(),
) -> EvidenceRecord:
    return EvidenceRecord(
        "mock_tool_io",
        "runtime_evidence",
        EvidencePhase.AFTER,
        {"calls": calls},
        correlation=correlation,
    )


def test_non_model_network_payload_is_minimized_before_evidence_archival() -> None:
    exchange = {
        "path": "/v2/plugin/accounts",
        "request_body": '{"account":"private"}',
        "response_body": '{"email":"private@example.invalid"}',
        "response_status": 200,
    }

    minimized = CodeBuddyAgentModel._network_evidence_exchange(exchange)

    assert minimized["request_body"] == "<omitted-non-model-payload>"
    assert minimized["response_body"] == "<omitted-non-model-payload>"
    assert minimized["response_status"] == 200
    assert exchange["response_body"] != minimized["response_body"]

    metadata = CodeBuddyAgentModel._network_exchange_metadata(minimized)
    assert "request_body" not in metadata
    assert "response_body" not in metadata
    assert len(metadata["request_body_sha256"]) == 64
    assert len(metadata["response_body_sha256"]) == 64
