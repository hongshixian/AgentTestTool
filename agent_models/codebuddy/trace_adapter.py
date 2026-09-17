"""Reconstruct a product-neutral Agent trace from CodeBuddy black-box evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from agent_models.evidence import EvidenceRecord, JsonValue
from agent_models.interaction import AgentEvent, AgentEventType
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


MODEL_PATH = "/v2/chat/completions"
_EXPLICIT_BACKGROUND_PROMPTS = frozenset(
    {
        "generate a short title",
        "summarize this session",
    }
)
_EXPLICIT_BACKGROUND_HEADER_TOKENS = {
    "x-agent-purpose": frozenset(
        {"background", "metadata", "summary", "title"}
    ),
    "x-agent-type": frozenset({"metadata", "summary", "title"}),
    "x-agent-intent": frozenset({"metadata", "summary", "title"}),
}


@dataclass(frozen=True, slots=True)
class TraceTurnIdentity:
    """Known public identifiers for a concurrently observable Agent turn."""

    turn_id: str
    prompt: str
    session_id: str
    task_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceTurnObservation:
    """Inputs observed for one evaluator-triggered CodeBuddy turn."""

    turn_id: str
    prompt: str
    session_id: str
    exchanges: tuple[Mapping[str, JsonValue], ...]
    started_at: str | None = None
    completed_at: str | None = None
    stream_events: tuple[AgentEvent, ...] = ()
    task_id: str | None = None
    competing_turns: tuple[TraceTurnIdentity, ...] = ()


@dataclass(slots=True)
class _ParsedCall:
    exchange: Mapping[str, JsonValue]
    request: dict[str, Any] | None
    response_events: list[dict[str, Any]]
    response_complete: bool
    response_parse_error_count: int = 0


class CodeBuddyTraceAdapter:
    """Merge captured model traffic, public stream events, and Mock MCP evidence."""

    def build(
        self,
        *,
        run_id: str,
        turns: Sequence[TraceTurnObservation],
        tool_records: Sequence[EvidenceRecord] = (),
        test_case_id: str | None = None,
        collector_health: str = "healthy",
        lost_event_count: int = 0,
        limitations: Sequence[str] = (),
    ) -> AgentTrace:
        sessions: dict[str, list[AgentTurn]] = {}
        tool_observations = _mock_tool_calls(tool_records)
        remaining_tools = list(tool_observations)
        trace_ready = TraceReadyState.READY
        trace_limitations = list(limitations)

        prepared_turns: list[
            tuple[TraceTurnObservation, list[_ParsedCall], int, int]
        ] = []
        proposal_turns: dict[str, set[str]] = {}
        for observation in turns:
            parsed_all = [
                _parse_exchange(exchange)
                for exchange in observation.exchanges
                if _is_model_exchange(exchange)
            ]
            parsed: list[_ParsedCall] = []
            background_count = 0
            ambiguous_count = 0
            for call in parsed_all:
                ownership = _call_ownership(call, observation)
                if ownership == "current":
                    parsed.append(call)
                elif ownership == "other":
                    background_count += 1
                else:
                    ambiguous_count += 1
            prepared_turns.append(
                (observation, parsed, background_count, ambiguous_count)
            )
            for call in parsed:
                for _, name, arguments in _response_content(call.response_events)[1]:
                    runtime_name, runtime_arguments = _runtime_tool_target(
                        name, arguments
                    )
                    key = _tool_match_key(runtime_name, runtime_arguments)
                    proposal_turns.setdefault(key, set()).add(observation.turn_id)

        ambiguous_cross_turn_keys = {
            key for key, turn_ids in proposal_turns.items() if len(turn_ids) > 1
        }
        for turn_index, (
            observation,
            parsed,
            background_count,
            ambiguous_count,
        ) in enumerate(prepared_turns):
            model_calls, turn_ready, turn_limits = self._build_turn_calls(
                observation,
                parsed,
                remaining_tools,
                ambiguous_cross_turn_keys,
            )
            if background_count:
                turn_limits.append(
                    f"已排除 {background_count} 个可归属其他任务或输入的"
                    "后台或元数据模型请求。"
                )
            if ambiguous_count:
                turn_limits.append(
                    f"有 {ambiguous_count} 个模型请求处于重叠观察窗口且"
                    "无法可靠归属，已从当前回合排除。"
                )
                if turn_ready is TraceReadyState.READY:
                    turn_ready = TraceReadyState.PARTIAL
            if turn_ready is not TraceReadyState.READY:
                trace_ready = TraceReadyState.PARTIAL
            turn = AgentTurn(
                turn_id=observation.turn_id,
                sequence=turn_index,
                user_input=observation.prompt,
                model_calls=tuple(model_calls),
                started_at=observation.started_at,
                completed_at=observation.completed_at,
                ready_state=turn_ready,
                limitations=tuple(turn_limits),
            )
            sessions.setdefault(observation.session_id, []).append(turn)

        if not sessions:
            trace_ready = TraceReadyState.UNAVAILABLE
            trace_limitations.append("未观察到可归属到 Agent 回合的模型网络交换。")
        if collector_health != "healthy" and trace_ready is TraceReadyState.READY:
            trace_ready = TraceReadyState.PARTIAL
        if remaining_tools:
            trace_limitations.append(
                "部分 Mock MCP 调用无法与已观察到的模型工具调用可靠关联。"
            )
            if trace_ready is TraceReadyState.READY:
                trace_ready = TraceReadyState.PARTIAL

        return AgentTrace(
            run_id=run_id,
            product="codebuddy",
            sessions=tuple(
                AgentSession(session_id, tuple(session_turns))
                for session_id, session_turns in sessions.items()
            ),
            test_case_id=test_case_id,
            started_at=_first_timestamp(turns, "started_at"),
            ended_at=_last_timestamp(turns, "completed_at"),
            ready_state=trace_ready,
            collector_health=collector_health,
            lost_event_count=lost_event_count,
            limitations=tuple(dict.fromkeys(trace_limitations)),
        )

    def _build_turn_calls(
        self,
        observation: TraceTurnObservation,
        calls: Sequence[_ParsedCall],
        remaining_tools: list[dict[str, JsonValue]],
        ambiguous_cross_turn_keys: set[str],
    ) -> tuple[list[ModelCall], TraceReadyState, list[str]]:
        if not calls:
            return [], TraceReadyState.UNAVAILABLE, [
                "该回合未捕获到 CodeBuddy 模型请求。"
            ]

        current_boundary = _current_message_boundary(calls, observation.prompt)
        remaining_stream_events = list(observation.stream_events)
        seen_tool_results: set[str] = set()
        sequence = 0
        built: list[ModelCall] = []
        limitations: list[str] = []
        ready = TraceReadyState.READY

        for call_index, parsed in enumerate(calls):
            exchange = parsed.exchange
            call_limitations: list[str] = []
            if parsed.request is None:
                call_limitations.append("模型请求正文不是可解析的 JSON。")
            if exchange.get("request_complete") is False:
                call_limitations.append("模型请求的网络传输没有完整结束。")
            if exchange.get("request_body_truncated") is True:
                call_limitations.append("模型请求正文超过采集上限并被截断。")
            if not parsed.response_events:
                call_limitations.append("模型响应正文没有可解析的 JSON 或 SSE 事件。")
            if not parsed.response_complete:
                call_limitations.append("模型响应未观察到完整结束边界。")
            if parsed.response_parse_error_count:
                call_limitations.append(
                    f"模型流式响应包含 {parsed.response_parse_error_count} 条无法解析的数据。"
                )
            if exchange.get("response_body_truncated") is True:
                call_limitations.append("模型响应正文超过采集上限并被截断。")
            if call_limitations:
                ready = TraceReadyState.PARTIAL
                limitations.extend(call_limitations)

            messages: list[TraceMessage] = []
            reasoning: list[TraceReasoning] = []
            tool_calls: list[TraceToolCall] = []
            tool_results: list[TraceToolResult] = []

            request_messages = _request_messages(parsed.request)
            visible_tools = _request_tools(parsed.request)
            for message_index, message in enumerate(request_messages):
                role = _text(message.get("role")) or _message_role(message)
                content = _message_content(message)
                returned = _tool_result_from_message(message)
                visibility = (
                    TraceVisibility.HISTORY
                    if message_index < current_boundary
                    else TraceVisibility.CURRENT
                )
                state = (
                    TraceReadyState.REPLAYED
                    if visibility is TraceVisibility.HISTORY
                    or (
                        returned is not None
                        and returned[0] in seen_tool_results
                    )
                    else TraceReadyState.READY
                )
                message_id = _stable_id(
                    "message", call_index, message_index, role, content
                )
                messages.append(
                    TraceMessage(
                        message_id,
                        role or "unknown",
                        cast(JsonValue, content),
                        sequence,
                        TracePhase.REQUEST,
                        visibility,
                        state,
                        _text(exchange.get("started_at")),
                        "network_interception",
                    )
                )
                sequence += 1
                if returned is not None:
                    tool_results.append(
                        TraceToolResult(
                            returned[0],
                            cast(JsonValue, returned[1]),
                            ToolCallStage.RETURNED,
                            sequence,
                            TracePhase.REQUEST,
                            visibility=visibility,
                            ready_state=state,
                            observed_at=_text(exchange.get("started_at")),
                            source="network_interception",
                        )
                    )
                    seen_tool_results.add(returned[0])
                    sequence += 1

            response_text, proposed, exposed_reasoning = _response_content(
                parsed.response_events
            )
            if response_text:
                messages.append(
                    TraceMessage(
                        _stable_id("assistant", call_index, response_text),
                        "assistant",
                        response_text,
                        sequence,
                        TracePhase.RESPONSE,
                        observed_at=_text(exchange.get("completed_at")),
                        source="network_interception",
                    )
                )
                sequence += 1
            for reasoning_index, content in enumerate(exposed_reasoning):
                reasoning.append(
                    TraceReasoning(
                        _stable_id("reasoning", call_index, reasoning_index, content),
                        cast(JsonValue, content),
                        sequence,
                        observed_at=_text(exchange.get("completed_at")),
                        source="network_interception",
                        limitations=(
                            "仅保存供应方在响应中显式返回的推理摘要或思考字段，不代表隐藏思维链。",
                        ),
                    )
                )
                sequence += 1

            for proposed_call in proposed:
                tool_call_id = proposed_call[0]
                name = proposed_call[1]
                arguments = proposed_call[2]
                runtime_name, runtime_arguments = _runtime_tool_target(name, arguments)
                tool_calls.append(
                    TraceToolCall(
                        tool_call_id,
                        name,
                        cast(JsonValue, arguments),
                        ToolCallStage.PROPOSED,
                        sequence,
                        TracePhase.RESPONSE,
                        observed_at=_text(exchange.get("completed_at")),
                        source="network_interception",
                    )
                )
                sequence += 1

                stream_match = _take_stream_tool_event(
                    remaining_stream_events, tool_call_id, name
                )
                if stream_match is not None:
                    tool_calls.append(
                        TraceToolCall(
                            tool_call_id,
                            name,
                            cast(JsonValue, arguments),
                            ToolCallStage.DISPATCHED,
                            sequence,
                            TracePhase.RUNTIME,
                            observed_at=stream_match.observed_at,
                            source="codebuddy_stream_json",
                        )
                    )
                    sequence += 1

                match_limitation: str | None = None
                actual, match_limitation = _take_matching_tool(
                    remaining_tools,
                    runtime_name,
                    runtime_arguments,
                    observation=observation,
                    ambiguous_across_turns=(
                        _tool_match_key(runtime_name, runtime_arguments)
                        in ambiguous_cross_turn_keys
                    ),
                )
                if match_limitation:
                    call_limitations.append(match_limitation)
                    limitations.append(match_limitation)
                    ready = TraceReadyState.PARTIAL
                if actual is not None:
                    actual_arguments = actual.get("arguments", runtime_arguments)
                    tool_calls.append(
                        TraceToolCall(
                            tool_call_id,
                            runtime_name,
                            cast(JsonValue, actual_arguments),
                            ToolCallStage.RECEIVED,
                            sequence,
                            TracePhase.RUNTIME,
                            source="controlled_mock_mcp",
                            limitations=(
                                "模型 Tool Call ID 未由 Mock MCP 公开传递；依据同一回合内的工具名、参数和顺序关联。",
                            ),
                        )
                    )
                    sequence += 1
                    tool_results.append(
                        TraceToolResult(
                            tool_call_id,
                            cast(JsonValue, actual.get("result")),
                            ToolCallStage.COMPLETED,
                            sequence,
                            TracePhase.RUNTIME,
                            is_error=bool(
                                isinstance(actual.get("result"), dict)
                                and actual["result"].get("isError")
                            ),
                            source="controlled_mock_mcp",
                        )
                    )
                    sequence += 1

            built.append(
                ModelCall(
                    model_call_id=_stable_id(
                        "model-call", exchange.get("exchange_id", call_index)
                    ),
                    sequence=call_index,
                    request_id=_request_id(exchange, parsed.response_events),
                    provider="codebuddy_openai_compatible",
                    endpoint=f"https://{_text(exchange.get('host')) or 'unknown'}{_text(exchange.get('path')) or MODEL_PATH}",
                    model=_text((parsed.request or {}).get("model")),
                    started_at=_text(exchange.get("started_at")),
                    completed_at=_text(exchange.get("completed_at")),
                    ready_state=(
                        TraceReadyState.READY
                        if not call_limitations
                        else TraceReadyState.PARTIAL
                    ),
                    messages=tuple(messages),
                    visible_tools=tuple(visible_tools),
                    reasoning=tuple(reasoning),
                    tool_calls=tuple(tool_calls),
                    tool_results=tuple(tool_results),
                    limitations=tuple(call_limitations),
                )
            )

        return built, ready, list(dict.fromkeys(limitations))


def _is_model_exchange(exchange: Mapping[str, JsonValue]) -> bool:
    method = (_text(exchange.get("method")) or "").upper()
    path = (_text(exchange.get("path")) or "").split("?", 1)[0]
    return method == "POST" and path == MODEL_PATH


def _parse_exchange(exchange: Mapping[str, JsonValue]) -> _ParsedCall:
    request = _json_object(exchange.get("request_body"))
    body = exchange.get("response_body")
    events, stream_done, parse_error_count = _response_events(body)
    response_complete = bool(exchange.get("response_complete", True)) and stream_done
    return _ParsedCall(
        exchange,
        request,
        events,
        response_complete,
        parse_error_count,
    )


def _json_object(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _response_events(value: object) -> tuple[list[dict[str, Any]], bool, int]:
    if isinstance(value, dict):
        return [dict(value)], True, 0
    if not isinstance(value, str) or not value.strip():
        return [], False, 0
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        events: list[dict[str, Any]] = []
        done = False
        parse_error_count = 0
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(":") or line.startswith(("event:", "id:", "retry:")):
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                done = True
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                parse_error_count += 1
                continue
            if isinstance(item, dict):
                events.append(item)
                if item.get("type") in {
                    "response.completed",
                    "message_stop",
                    "turn.completed",
                }:
                    done = True
                if any(
                    isinstance(choice, dict) and choice.get("finish_reason") is not None
                    for choice in item.get("choices", [])
                    if isinstance(item.get("choices"), list)
                ):
                    done = True
            else:
                parse_error_count += 1
        return events, done, parse_error_count
    if isinstance(payload, dict):
        return [payload], True, 0
    if isinstance(payload, list):
        events = [item for item in payload if isinstance(item, dict)]
        return events, True, len(payload) - len(events)
    return [], False, 1


def _call_ownership(
    call: _ParsedCall,
    observation: TraceTurnObservation,
) -> str:
    """Return current, other, or ambiguous without guessing across windows."""

    current = TraceTurnIdentity(
        observation.turn_id,
        observation.prompt,
        observation.session_id,
        observation.task_id,
    )
    if _is_explicit_background_call(call, observation.prompt):
        return "other"
    identities = (current, *observation.competing_turns)
    candidates: tuple[TraceTurnIdentity, ...] = identities

    identifiers = _call_identifiers(call)
    for kind in ("task_id", "turn_id", "session_id"):
        values = identifiers[kind]
        if not values:
            continue
        matched = tuple(
            identity
            for identity in candidates
            if getattr(identity, kind) in values
        )
        if not matched:
            return "other"
        candidates = matched
        if len(candidates) == 1:
            return "current" if candidates[0].turn_id == current.turn_id else "other"

    messages = _request_messages(call.request)
    scores = {
        identity.turn_id: _prompt_match_score(messages, identity.prompt)
        for identity in candidates
    }
    best_score = max(scores.values(), default=0)
    if best_score <= 0:
        return "ambiguous"
    winners = tuple(
        identity
        for identity in candidates
        if scores[identity.turn_id] == best_score
    )
    if len(winners) != 1:
        return "ambiguous"
    return "current" if winners[0].turn_id == current.turn_id else "other"


def _is_explicit_background_call(call: _ParsedCall, current_prompt: str) -> bool:
    headers = call.exchange.get("request_headers")
    if isinstance(headers, Mapping):
        for name, background_tokens in _EXPLICIT_BACKGROUND_HEADER_TOKENS.items():
            value = next(
                (
                    item
                    for key, item in headers.items()
                    if str(key).casefold() == name
                ),
                None,
            )
            if not isinstance(value, str):
                continue
            tokens = {
                token
                for token in value.casefold().replace("-", "_").split("_")
                if token
            }
            if tokens & background_tokens:
                return True

    normalized_current = current_prompt.strip().casefold().rstrip(".。")
    for message in _request_messages(call.request):
        if _message_role(message) != "user":
            continue
        content = _content_text(_message_content(message)).strip().casefold()
        normalized = content.rstrip(".。")
        if normalized == normalized_current:
            continue
        if normalized in _EXPLICIT_BACKGROUND_PROMPTS:
            return True
    return False


def _call_identifiers(call: _ParsedCall) -> dict[str, set[str]]:
    headers = call.exchange.get("request_headers")
    header_map = (
        {str(key).casefold(): value for key, value in headers.items()}
        if isinstance(headers, Mapping)
        else {}
    )
    result = {
        "task_id": _header_identifiers(
            header_map, "x-task-id", "x-agent-task-id"
        ),
        "turn_id": _header_identifiers(
            header_map, "x-turn-id", "x-agent-turn-id"
        ),
        "session_id": _header_identifiers(
            header_map, "x-conversation-id", "x-session-id"
        ),
    }
    request = call.request
    while isinstance(request, Mapping):
        _add_identifier(result["task_id"], request, "task_id", "taskId")
        _add_identifier(result["turn_id"], request, "turn_id", "turnId")
        _add_identifier(
            result["session_id"],
            request,
            "session_id",
            "sessionId",
            "conversation_id",
            "conversationId",
        )
        nested = request.get("request")
        request = nested if isinstance(nested, Mapping) else None
    return result


def _header_identifiers(
    headers: Mapping[str, object], *names: str
) -> set[str]:
    return {
        value.strip()
        for name in names
        if isinstance((value := headers.get(name)), str) and value.strip()
    }


def _add_identifier(
    target: set[str], source: Mapping[str, object], *names: str
) -> None:
    for name in names:
        value = source.get(name)
        if isinstance(value, str) and value.strip():
            target.add(value.strip())


def _prompt_match_score(
    messages: Sequence[Mapping[str, Any]], prompt: str
) -> int:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        return 0
    score = 0
    wrapped_prompt = f"<user_query>{normalized_prompt}</user_query>"
    for message in messages:
        if _message_role(message) != "user":
            continue
        content = _content_text(_message_content(message)).strip()
        if content == normalized_prompt or wrapped_prompt in content:
            score = max(score, 2)
        elif normalized_prompt in content:
            score = max(score, 1)
    return score


def _request_messages(request: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if request is None:
        return []
    for key in ("messages", "input", "contents"):
        value = request.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
    nested = request.get("request")
    return _request_messages(nested) if isinstance(nested, dict) else []


def _request_tools(request: Mapping[str, Any] | None) -> list[JsonValue]:
    if request is None:
        return []
    value = request.get("tools")
    if isinstance(value, list):
        return [cast(JsonValue, dict(item)) for item in value if isinstance(item, dict)]
    nested = request.get("request")
    return _request_tools(nested) if isinstance(nested, dict) else []


def _current_message_boundary(calls: Sequence[_ParsedCall], prompt: str) -> int:
    messages = _request_messages(calls[0].request) if calls else []
    normalized_prompt = prompt.strip()
    for index in range(len(messages) - 1, -1, -1):
        if _message_role(messages[index]) != "user":
            continue
        if normalized_prompt and normalized_prompt in _content_text(
            _message_content(messages[index])
        ):
            return index
    user_indices = [
        index
        for index, message in enumerate(messages)
        if _message_role(message) == "user"
    ]
    return user_indices[-1] if user_indices else len(messages)


def _message_role(message: Mapping[str, Any]) -> str:
    role = message.get("role")
    if isinstance(role, str):
        return role
    message_type = message.get("type")
    if message_type in {"input_text", "input_image", "message"}:
        return "user"
    if message_type in {"function_call_output", "tool_result"}:
        return "tool"
    return "unknown"


def _message_content(message: Mapping[str, Any]) -> JsonValue:
    if "content" in message:
        return cast(JsonValue, message["content"])
    if "text" in message:
        return cast(JsonValue, message["text"])
    return cast(JsonValue, dict(message))


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            _content_text(item.get("text") if isinstance(item, dict) else item)
            for item in content
        )
    if isinstance(content, dict):
        return _content_text(content.get("text") or content.get("content") or "")
    return ""


def _tool_result_from_message(
    message: Mapping[str, Any],
) -> tuple[str, JsonValue] | None:
    role = _message_role(message)
    message_type = message.get("type")
    if role != "tool" and message_type not in {"function_call_output", "tool_result"}:
        return None
    identifier = (
        message.get("tool_call_id")
        or message.get("call_id")
        or message.get("tool_use_id")
        or message.get("id")
    )
    if not isinstance(identifier, str) or not identifier:
        return None
    content = message.get("content", message.get("output", message.get("result")))
    return identifier, cast(JsonValue, content)


def _response_content(
    events: Sequence[Mapping[str, Any]],
) -> tuple[str, list[tuple[str, str, JsonValue]], list[JsonValue]]:
    text_parts: list[str] = []
    reasoning: list[JsonValue] = []
    tools: dict[int | str, dict[str, Any]] = {}

    for event in events:
        choices = event.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                payload = choice.get("delta") or choice.get("message") or {}
                if isinstance(payload, dict):
                    content = payload.get("content")
                    if isinstance(content, str):
                        text_parts.append(content)
                    _append_reasoning(reasoning, payload)
                    _merge_tool_calls(tools, payload.get("tool_calls"))
        event_type = event.get("type")
        if event_type in {"response.output_text.delta", "content_block_delta"}:
            delta = event.get("delta")
            if isinstance(delta, str):
                text_parts.append(delta)
            elif isinstance(delta, dict) and isinstance(delta.get("text"), str):
                text_parts.append(delta["text"])
        _append_reasoning(reasoning, event)
        _merge_response_output(tools, text_parts, reasoning, event.get("output"))

    proposed: list[tuple[str, str, JsonValue]] = []
    for key, tool in tools.items():
        identifier = _text(tool.get("id")) or _text(tool.get("call_id"))
        name = _text(tool.get("name"))
        arguments = tool.get("arguments", {})
        if not identifier:
            identifier = _stable_id("tool-call", key, name, arguments)
        if name:
            proposed.append((identifier, name, cast(JsonValue, _parse_arguments(arguments))))
    return "".join(text_parts), proposed, _coalesce_reasoning(reasoning)


def _coalesce_reasoning(values: Sequence[JsonValue]) -> list[JsonValue]:
    """Join streamed reasoning deltas without merging structured summaries."""

    result: list[JsonValue] = []
    text_parts: list[str] = []

    def flush_text() -> None:
        if text_parts:
            result.append("".join(text_parts))
            text_parts.clear()

    for value in values:
        if isinstance(value, str):
            text_parts.append(value)
        else:
            flush_text()
            result.append(value)
    flush_text()
    return result


def _append_reasoning(target: list[JsonValue], payload: Mapping[str, Any]) -> None:
    for key in ("reasoning", "reasoning_content", "thinking", "thinking_summary"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            target.append(cast(JsonValue, value))


def _merge_tool_calls(target: dict[int | str, dict[str, Any]], value: object) -> None:
    if not isinstance(value, list):
        return
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        key = cast(int | str, item.get("index", item.get("id", position)))
        current = target.setdefault(key, {})
        identifier = item.get("id") or item.get("call_id")
        if identifier:
            current["id"] = identifier
        function = item.get("function")
        if isinstance(function, dict):
            if function.get("name"):
                current["name"] = function["name"]
            if isinstance(function.get("arguments"), str):
                current["arguments"] = str(current.get("arguments", "")) + function["arguments"]
            elif "arguments" in function:
                current["arguments"] = function["arguments"]
        else:
            if item.get("name"):
                current["name"] = item["name"]
            if "arguments" in item:
                current["arguments"] = item["arguments"]


def _merge_response_output(
    tools: dict[int | str, dict[str, Any]],
    texts: list[str],
    reasoning: list[JsonValue],
    value: object,
) -> None:
    if not isinstance(value, list):
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"function_call", "tool_call"}:
            _merge_tool_calls(tools, [{**item, "index": index}])
        elif item_type in {"reasoning", "thinking"}:
            reasoning.append(cast(JsonValue, item.get("summary", item.get("content", item))))
        elif item_type in {"message", "output_text"}:
            content = _content_text(item.get("content", item.get("text", "")))
            if content:
                texts.append(content)


def _parse_arguments(value: object) -> JsonValue:
    if not isinstance(value, str):
        return cast(JsonValue, value)
    try:
        return cast(JsonValue, json.loads(value))
    except json.JSONDecodeError:
        return value


def _request_id(
    exchange: Mapping[str, JsonValue], events: Sequence[Mapping[str, Any]]
) -> str | None:
    headers = exchange.get("response_headers")
    if isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() in {"x-request-id", "request-id", "trace-id"}:
                return _text(value)
    for event in events:
        value = event.get("id") or event.get("request_id")
        if isinstance(value, str) and value:
            return value
    return None


def _mock_tool_calls(records: Sequence[EvidenceRecord]) -> list[dict[str, JsonValue]]:
    calls: list[dict[str, JsonValue]] = []
    for record in records:
        if record.evidence_id != "mock_tool_io" or not record.available:
            continue
        if not isinstance(record.data, dict) or not isinstance(record.data.get("calls"), list):
            continue
        correlation: dict[str, JsonValue] = {
            "session_ids": list(record.correlation.session_ids),
            "turn_ids": list(record.correlation.turn_ids),
            "task_ids": list(record.correlation.task_ids),
        }
        for item in record.data["calls"]:
            if not isinstance(item, dict):
                continue
            call = dict(item)
            call.setdefault("_evidence_correlation", correlation)
            calls.append(call)
    return calls


def _take_matching_tool(
    remaining: list[dict[str, JsonValue]],
    name: str,
    arguments: JsonValue,
    *,
    observation: TraceTurnObservation,
    ambiguous_across_turns: bool,
) -> tuple[dict[str, JsonValue] | None, str | None]:
    all_name_matches = [
        (index, item)
        for index, item in enumerate(remaining)
        if _tool_names_match(item.get("tool_name"), name)
    ]
    arguments_known = arguments not in ({}, "", None)
    all_exact_matches = [
        (index, item)
        for index, item in all_name_matches
        if not arguments_known or item.get("arguments") == arguments
    ]
    if observation.competing_turns:
        name_matches = [
            (index, item)
            for index, item in all_name_matches
            if _tool_call_matches_turn(item, observation)
        ]
        if all_exact_matches and not any(
            _tool_call_matches_turn(item, observation)
            for _, item in all_exact_matches
        ):
            return None, (
                "重叠任务中存在同名同参数 Mock MCP 调用，但该调用缺少可验证的"
                "相同 task/session/turn 关联，不能归属当前回合。"
            )
    else:
        name_matches = all_name_matches
        if ambiguous_across_turns and name_matches:
            return None, (
                "同名同参数 Mock MCP 提议跨多个回合出现，缺少可验证的回合关联标识。"
            )
    if arguments_known:
        exact = [
            (index, item)
            for index, item in name_matches
            if item.get("arguments") == arguments
        ]
        if len(exact) == 1:
            return remaining.pop(exact[0][0]), None
        if len(exact) > 1:
            return None, "多个 Mock MCP 调用具有相同工具名和参数，无法唯一关联。"
        if name_matches:
            return None, "Mock MCP 工具名匹配，但实际参数与模型提议不一致。"
        return None, None
    if len(name_matches) == 1:
        return remaining.pop(name_matches[0][0]), None
    if len(name_matches) > 1:
        return None, "模型工具参数不可用且存在多个同名 Mock MCP 调用，无法唯一关联。"
    return None, None


def _tool_call_matches_turn(
    item: Mapping[str, JsonValue], observation: TraceTurnObservation
) -> bool:
    raw = item.get("correlation", item.get("_evidence_correlation"))
    if not isinstance(raw, Mapping):
        return False
    current = TraceTurnIdentity(
        observation.turn_id,
        observation.prompt,
        observation.session_id,
        observation.task_id,
    )
    identities = (current, *observation.competing_turns)
    fields = (
        ("task_ids", "task_id"),
        ("turn_ids", "turn_id"),
        ("session_ids", "session_id"),
    )
    for plural, singular in fields:
        values = {
            value
            for value in raw.get(plural, ())
            if isinstance(value, str) and value
        } if isinstance(raw.get(plural, ()), (list, tuple)) else set()
        if not values:
            continue
        matching_turn_ids = {
            identity.turn_id
            for identity in identities
            if getattr(identity, singular) in values
        }
        if current.turn_id not in matching_turn_ids:
            return False
        if matching_turn_ids == {current.turn_id}:
            return True
        return False
    return False


def _runtime_tool_target(name: str, arguments: JsonValue) -> tuple[str, JsonValue]:
    if name != "DeferExecuteTool" or not isinstance(arguments, dict):
        return name, arguments
    target = arguments.get("tool_name") or arguments.get("toolName")
    nested = arguments.get("params", arguments.get("arguments", {}))
    if isinstance(nested, str):
        nested = _parse_arguments(nested)
    if isinstance(target, str) and target:
        return target, cast(JsonValue, nested)
    return name, arguments


def _tool_match_key(name: str, arguments: JsonValue) -> str:
    return _stable_id("tool-match", name, arguments)


def _tool_names_match(observed: object, expected: str) -> bool:
    if not isinstance(observed, str):
        return False
    return observed == expected or expected.endswith(f"__{observed}") or observed.endswith(
        f"__{expected}"
    )


def _take_stream_tool_event(
    events: list[AgentEvent], tool_call_id: str, name: str
) -> AgentEvent | None:
    for index, event in enumerate(events):
        if event.event_type is not AgentEventType.TOOL_CALL or not isinstance(event.data, dict):
            continue
        identifier = (
            event.data.get("id")
            or event.data.get("tool_use_id")
            or event.data.get("toolUseId")
        )
        if identifier == tool_call_id:
            return events.pop(index)
    for index, event in enumerate(events):
        if event.event_type is not AgentEventType.TOOL_CALL or not isinstance(event.data, dict):
            continue
        identifier = (
            event.data.get("id")
            or event.data.get("tool_use_id")
            or event.data.get("toolUseId")
        )
        event_name = event.data.get("name") or event.data.get("tool_name")
        if identifier is None and event_name == name:
            return events.pop(index)
    return None


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=True, sort_keys=True, default=str).encode()
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:20]}"


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _first_timestamp(turns: Sequence[TraceTurnObservation], field: str) -> str | None:
    return next(
        (
            value
            for turn in turns
            if isinstance((value := getattr(turn, field)), str) and value
        ),
        None,
    )


def _last_timestamp(turns: Sequence[TraceTurnObservation], field: str) -> str | None:
    return next(
        (
            value
            for turn in reversed(turns)
            if isinstance((value := getattr(turn, field)), str) and value
        ),
        None,
    )


__all__ = ["CodeBuddyTraceAdapter", "TraceTurnIdentity", "TraceTurnObservation"]
