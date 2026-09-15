"""Deterministic assertions over reconstructed black-box Agent traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_models.evidence import EvidenceBundle, EvidenceRecord
from evidence_collectors.trace import ToolCallStage


def assert_reconstructed_trace_ready(
    bundle_or_records: EvidenceBundle | Sequence[EvidenceRecord],
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> None:
    """Require a healthy, complete reconstructed trace before factual assertions."""

    record = _available_record(bundle_or_records, "reconstructed_agent_trace")
    trace = _mapping(record.data, "重建 Trace 数据必须是对象")
    assert trace.get("ready_state") == "ready", "Agent Trace 不完整，不能给出确定性结论"
    assert trace.get("collector_health") == "healthy", "Trace 采集器不健康"
    assert trace.get("lost_event_count") == 0, "Trace 存在丢失事件"
    turn = _selected_turn(trace, session_id=session_id, turn_id=turn_id)
    assert turn.get("ready_state", "ready") == "ready", "所选 Agent 回合 Trace 不完整"
    assert _sequence(turn.get("model_calls")), "所选 Agent 回合中没有模型调用"


def assert_model_context_contains(
    bundle_or_records: EvidenceBundle | Sequence[EvidenceRecord],
    expected_text: str,
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
    visibility: str = "current",
) -> None:
    """Require text in an actually observed model-request message."""

    assert isinstance(expected_text, str) and expected_text, "必须提供非空预期文本"
    record = _available_record(bundle_or_records, "reconstructed_agent_trace")
    data = _mapping(record.data, "重建 Trace 数据必须是对象")
    turn = _selected_turn(data, session_id=session_id, turn_id=turn_id)
    messages = [
        message
        for call in _sequence(turn.get("model_calls"))
        if isinstance(call, Mapping)
        for message in _sequence(call.get("messages"))
        if isinstance(message, Mapping)
        and message.get("phase") == "request"
        and message.get("visibility") == visibility
    ]
    assert messages, "没有符合可见性要求的模型请求消息"
    assert any(expected_text in _text_content(item.get("content")) for item in messages), (
        "模型请求中未观察到预期文本"
    )


def assert_tool_lifecycle(
    bundle_or_records: EvidenceBundle | Sequence[EvidenceRecord],
    tool_name: str,
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
    expected_arguments: Mapping[str, Any] | None = None,
    required_stages: Sequence[ToolCallStage | str] = (
        ToolCallStage.PROPOSED,
        ToolCallStage.RECEIVED,
        ToolCallStage.COMPLETED,
        ToolCallStage.RETURNED,
    ),
) -> None:
    """Require one correlated tool chain, including evaluator-observed execution."""

    assert isinstance(tool_name, str) and tool_name, "必须指定工具名称"
    record = _available_record(bundle_or_records, "reconstructed_agent_trace")
    trace = _mapping(record.data, "重建 Trace 数据必须是对象")
    turn = _selected_turn(trace, session_id=session_id, turn_id=turn_id)
    events: list[Mapping[str, Any]] = []
    for call in _sequence(turn.get("model_calls")):
        if not isinstance(call, Mapping):
            continue
        events.extend(
            item
            for key in ("tool_calls", "tool_results")
            for item in _sequence(call.get(key))
            if isinstance(item, Mapping)
            and item.get("ready_state", "ready") != "replayed"
        )
    candidate_ids = {
        item.get("tool_call_id")
        for item in events
        if _event_matches_tool(item, tool_name, expected_arguments)
        and isinstance(item.get("tool_call_id"), str)
    }
    assert candidate_ids, "Trace 中未观察到指定工具"
    desired = tuple(
        stage.value if isinstance(stage, ToolCallStage) else str(stage)
        for stage in required_stages
    )
    stage_rank = {stage.value: index for index, stage in enumerate(ToolCallStage)}
    for identifier in candidate_ids:
        correlated = [item for item in events if item.get("tool_call_id") == identifier]
        stages = [str(item.get("stage")) for item in correlated]
        if not all(stage in stages for stage in desired):
            continue
        sequence = [int(item.get("sequence", -1)) for item in correlated]
        ordered = [
            stage
            for _, stage in sorted(zip(sequence, stages), key=lambda pair: pair[0])
            if stage in stage_rank
        ]
        if [stage_rank[item] for item in ordered] == sorted(
            stage_rank[item] for item in ordered
        ):
            return
    raise AssertionError("指定工具缺少完整且有序的关联生命周期")


def _available_record(
    bundle_or_records: EvidenceBundle | Sequence[EvidenceRecord], evidence_id: str
) -> EvidenceRecord:
    records = (
        bundle_or_records.records
        if isinstance(bundle_or_records, EvidenceBundle)
        else tuple(bundle_or_records)
    )
    matches = [record for record in records if record.evidence_id == evidence_id]
    assert len(matches) == 1, f"证据 {evidence_id} 缺失或不唯一"
    assert matches[0].available, f"证据 {evidence_id} 不可用于事实断言"
    return matches[0]


def _mapping(value: object, message: str) -> Mapping[str, Any]:
    assert isinstance(value, Mapping), message
    return value


def _selected_turn(
    trace: Mapping[str, Any], *, session_id: str | None, turn_id: str | None
) -> Mapping[str, Any]:
    assert session_id is None or (
        isinstance(session_id, str) and session_id
    ), "session_id 必须为非空字符串"
    assert turn_id is None or (
        isinstance(turn_id, str) and turn_id
    ), "turn_id 必须为非空字符串"
    sessions = [
        session
        for session in _sequence(trace.get("sessions"))
        if isinstance(session, Mapping)
        and (session_id is None or session.get("session_id") == session_id)
    ]
    assert len(sessions) == 1, (
        "Trace 中存在多个或没有 Agent 会话，必须指定唯一 session_id"
    )
    turns = [
        turn
        for turn in _sequence(sessions[0].get("turns"))
        if isinstance(turn, Mapping)
        and (turn_id is None or turn.get("turn_id") == turn_id)
    ]
    assert len(turns) == 1, (
        "Trace 中存在多个或没有 Agent 回合，必须指定唯一 turn_id"
    )
    return turns[0]


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else ()


def _text_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return "\n".join(_text_content(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "\n".join(_text_content(item) for item in value)
    return ""


def _tool_name_matches(value: object, expected: str) -> bool:
    return isinstance(value, str) and (
        value == expected
        or value.endswith(f"__{expected}")
        or expected.endswith(f"__{value}")
    )


def _event_matches_tool(
    event: Mapping[str, Any],
    expected: str,
    expected_arguments: Mapping[str, Any] | None,
) -> bool:
    arguments = event.get("arguments")
    if _tool_name_matches(event.get("name"), expected):
        return expected_arguments is None or arguments == expected_arguments
    if not isinstance(arguments, Mapping):
        return False
    nested = arguments.get("params", arguments.get("arguments"))
    return _tool_name_matches(
        arguments.get("tool_name") or arguments.get("toolName"), expected
    ) and (expected_arguments is None or nested == expected_arguments)


__all__ = [
    "assert_model_context_contains",
    "assert_reconstructed_trace_ready",
    "assert_tool_lifecycle",
]
