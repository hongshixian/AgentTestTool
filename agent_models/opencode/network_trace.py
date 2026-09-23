"""Fail-closed reconstruction of explicitly correlated OpenCode IIIS traffic."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agent_models.evidence import (
    EvidenceAuthority, EvidenceCorrelation, EvidencePhase, EvidenceRecord,
    EvidenceRequest, EvidenceSource, EvidenceStatus, JsonValue,
)
from evidence_collectors.trace import (
    AgentSession, AgentTrace, AgentTurn, ModelCall, ToolCallStage, TraceMessage,
    TracePhase, TraceReadyState, TraceToolCall, TraceToolResult,
    TraceVisibility,
)


MODEL_PATH = "/v1/chat/completions"
_MAX_EXCHANGES = 64
_MAX_BODY_BYTES = 2 * 1024 * 1024
_WIRE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,256}\Z")
_COMMON_LIMITATIONS = (
    "Only explicitly intercepted model traffic in this evaluator-owned window is represented.",
    "x-turn-id is an evaluator-owned one-shot correlation nonce injected by a grey-box plugin, not a product-generated turn ID.",
    "x-ats-oc-agent is an evaluator-injected OpenCode agent label; title generation stays in network metadata only.",
    "x-litellm-call-id identifies an IIIS LiteLLM proxy call, not an independent upstream model-provider request.",
    "Response tool proposals and request tool results alone do not prove external side effects.",
    "Hidden model reasoning, other transports and uncaptured background work are not observable.",
)
_DEGRADED_LIMITATION = (
    "The overall HTTPS collector window is unhealthy because classified OpenCode title responses ended incomplete; "
    "only complete primary build calls support this trace, and no all-traffic or absence claim is made."
)
_WINDOW_UNHEALTHY_LIMITATION = (
    "The overall HTTPS collector window is unhealthy; only independently verified primary build requests may support a trace."
)
_DIAGNOSTIC_FIELDS = frozenset({
    "retained_error_types", "unattributed_error_count", "dropped_error_count", "resource_limits",
})


@dataclass(frozen=True, slots=True)
class _Parsed:
    exchange: Mapping[str, Any]
    request_id: str
    request: dict[str, Any]
    text: str
    tool_calls: tuple[dict[str, Any], ...]
    response_id: str


class OpenCodeNetworkTrace:
    """Interpret one complete, exclusive, intercepted per-turn observation window.

    The proxy's local ``exchange_id`` does not establish provider or turn
    identity. A READY trace requires OpenCode's native x-session-id, a matching
    evaluator-injected x-turn-id and classified agent on *every* scoped model
    request. Only primary build calls need unique IIIS x-litellm-call-id
    response headers and completed SSE framing: title generation is excluded
    from the trajectory even when its response is incomplete. Unclassified or
    ambiguous background requests prevent a READY trace.
    """

    def capture(
        self,
        request: EvidenceRequest,
        *,
        exchanges: Sequence[Mapping[str, Any]],
        run_id: str,
        prompt: str,
        session_id: str,
        turn_id: str,
        window_start: str,
        window_end: str,
        provider_host: str,
        collector_healthy: bool,
        collector_diagnostics: Mapping[str, Any] | None = None,
        redactor: Callable[[Any], JsonValue] | None = None,
        competing_turns: bool = False,
        product_version: str | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        if request.phase is not EvidencePhase.AFTER:
            return ()
        if not run_id or (request.context and request.context.run_id != run_id):
            raise ValueError("run identity mismatch")
        if not all(isinstance(x, str) and x for x in (
            prompt, session_id, turn_id, window_start, window_end, provider_host
        )):
            raise ValueError("network trace needs explicit turn window and provider host")
        if request.session_id is not None and request.session_id != session_id:
            raise ValueError("session identity mismatch")
        source = EvidenceSource(
            provider="https_mitm", channel="explicit_iiis_https_interception",
            authority=EvidenceAuthority.EVALUATOR_OBSERVED,
            product="opencode", product_version=product_version,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        limited = len(exchanges) <= _MAX_EXCHANGES
        limitations = (*_COMMON_LIMITATIONS, *((_WINDOW_UNHEALTHY_LIMITATION,) if not collector_healthy else ()))
        metadata: list[dict[str, JsonValue]] = []
        if limited:
            for item in exchanges:
                metadata.append({
                    "exchange_id": _short(item.get("exchange_id")),
                    "sequence": item.get("sequence") if isinstance(item.get("sequence"), int) else None,
                    "host": _short(item.get("host")),
                    "path": MODEL_PATH if item.get("path") == MODEL_PATH else "[other]",
                    "intercepted": item.get("intercepted") is True,
                    "request_complete": item.get("request_complete") is True,
                    "response_complete": item.get("response_complete") is True,
                    "response_status": item.get("response_status") if isinstance(item.get("response_status"), int) else None,
                    "request_sha256": _digest(item.get("request_body")),
                    "response_sha256": _digest(item.get("response_body")),
                })
        network = EvidenceRecord(
            "network_exchange_trace", "network_evidence", request.phase,
            {"exchanges": metadata},
            status=EvidenceStatus.AVAILABLE if metadata and collector_healthy else EvidenceStatus.UNVERIFIED,
            source=source, correlation=EvidenceCorrelation(run_id=run_id),
            proves=("Evaluator observed bounded HTTPS exchange metadata for the selected window",)
            if metadata and collector_healthy else (),
            limitations=(*limitations,
                         "Metadata digests are of the collector's redacted copies, not original wire bytes."),
        )

        def incomplete(reason: str) -> tuple[EvidenceRecord, ...]:
            status = EvidenceStatus.UNVERIFIED if exchanges else EvidenceStatus.MISSING
            return (network, *(EvidenceRecord(
                identifier, "collection_diagnostic", request.phase,
                {}, status=status, source=source,
                correlation=EvidenceCorrelation(run_id=run_id),
                limitations=(*limitations, reason),
            ) for identifier in (
                "reconstructed_agent_trace", "observed_model_context",
                "observed_model_output", "observed_tool_trace",
            )))

        if not limited or competing_turns or redactor is None:
            return incomplete("Collector/window/turn ownership or redaction is not verified")
        try:
            if not collector_healthy and not _title_only_degradation(
                exchanges, session_id=session_id, turn_id=turn_id,
                provider_host=provider_host, diagnostics=collector_diagnostics,
            ):
                raise ValueError("unattributed collector degradation")
            if not collector_healthy:
                limitations = (*_COMMON_LIMITATIONS, _DEGRADED_LIMITATION)
            start, end = _parse_time(window_start), _parse_time(window_end)
            if end < start:
                raise ValueError("reversed observation window")
            if sum(
                len(value.encode("utf-8"))
                for item in exchanges
                for key in ("request_body", "response_body")
                if isinstance((value := item.get(key)), str)
            ) > _MAX_BODY_BYTES:
                raise ValueError("run-scoped network body budget exceeded")
            parsed = []
            for item in exchanges:
                started = _parse_time(item.get("started_at"))
                if started < start or started > end:
                    raise ValueError("exchange outside exclusive turn window")
                if item.get("host") != provider_host or item.get("path") != MODEL_PATH:
                    completed = _parse_time(item.get("completed_at"))
                    if completed < started or completed > end:
                        raise ValueError("exchange outside exclusive turn window")
                    # A CONNECT tunnel to the provider may hide uncaptured model
                    # calls. Don't claim complete coverage while it is present.
                    if item.get("host") == provider_host:
                        raise ValueError("provider traffic could not be fully intercepted")
                    if item.get("path") == MODEL_PATH:
                        raise ValueError("background model traffic to another host")
                    continue
                agent, _ = _model_request(item, session_id, turn_id)
                completed_at = item.get("completed_at")
                if completed_at is None:
                    # A pending title response has no terminal timestamp, but
                    # its complete, classified request still remains metadata.
                    if agent != "title" or item.get("response_complete") is True:
                        raise ValueError("main model exchange has no completion timestamp")
                else:
                    completed = _parse_time(completed_at)
                    if completed < started or completed > end:
                        raise ValueError("exchange outside exclusive turn window")
                if agent == "build":
                    parsed.append(_parse_exchange(item, prompt, session_id, turn_id, redactor))
            if not parsed:
                raise ValueError("no correlated model exchange")
            parsed.sort(key=lambda call: (call.exchange["started_at"], call.exchange["sequence"]))
            if len({call.request_id for call in parsed}) != len(parsed):
                raise ValueError("ambiguous reused IIIS LiteLLM call id")
            # A unique, explicit model turn must include its current user prompt
            # even when the final model call contains only a tool result.
            if not _has_prompt(parsed[0].request, prompt):
                raise ValueError("current prompt absent from first model call")
            trace, contexts, outputs, tool_trace = _build_trace(
                parsed, run_id=run_id, prompt=prompt, session_id=session_id,
                turn_id=turn_id, redactor=redactor,
                collector_health="healthy" if collector_healthy else "title_response_degraded",
                limitations=limitations,
            )
        except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
            # Exception details may contain credentials or user content.
            return incomplete("Network exchange lacks trustworthy turn correlation or complete framing")
        correlation = EvidenceCorrelation(
            run_id=run_id, session_ids=(session_id,), turn_ids=(turn_id,),
            request_ids=tuple(item.request_id for item in parsed),
            tool_use_ids=tuple(sorted({tool["id"] for item in parsed for tool in item.tool_calls})),
        )
        return (
            network,
            EvidenceRecord(
                "reconstructed_agent_trace", "agent_trace_evidence", request.phase,
                trace.to_payload(), source=source, correlation=correlation,
                proves=("Observed complete, explicitly correlated IIIS request and response bodies",),
                limitations=limitations,
            ),
            EvidenceRecord(
                "observed_model_context", "agent_trace_evidence", request.phase,
                {"model_calls": contexts}, source=source, correlation=correlation,
                proves=("Actual model request messages and declared tools on the selected turn",),
                limitations=limitations,
            ),
            EvidenceRecord(
                "observed_model_output", "agent_trace_evidence", request.phase,
                {"model_calls": outputs}, source=source, correlation=correlation,
                proves=("Actual model response text and tool proposals on the selected turn",),
                limitations=limitations,
            ),
            EvidenceRecord(
                "observed_tool_trace", "agent_trace_evidence", request.phase,
                {"model_calls": tool_trace},
                status=EvidenceStatus.AVAILABLE if any(item.tool_calls for item in parsed) else EvidenceStatus.MISSING,
                source=source, correlation=correlation,
                proves=("Actually observed model tool proposal and later returned model-visible result",)
                if any(item.tool_calls for item in parsed) else (),
                limitations=(*limitations, "Tool execution requires separate product runtime or mock receiver proof."),
            ),
        )


def _short(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:200] if len(value) <= 200 else "[oversized]"


def _digest(value: Any) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if isinstance(value, str) else None


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing exchange timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("exchange timestamp must be timezone-aware")
    return parsed


def _headers(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    headers: dict[str, str] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str):
            continue
        name = key.casefold()
        if name in headers:
            raise ValueError("ambiguous case-insensitive wire header")
        headers[name] = val
    return headers


def _required_header(headers: Mapping[str, str], name: str) -> str:
    value = headers.get(name)
    if not isinstance(value, str) or not _WIRE_ID.fullmatch(value):
        raise ValueError("missing or ambiguous wire correlation header")
    return value


def _has_prompt(req: Mapping[str, Any], prompt: str) -> bool:
    messages = req.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = _content_text(message.get("content")).strip()
        if content == prompt.strip():
            return True
        # OpenCode 1.18.32 can encode the submitted user text as one JSON string.
        # Decode exactly one string; never accept a substring or adjacent text.
        if content.startswith('"') and content.endswith('"'):
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, str) and decoded == prompt:
                return True
    return False


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            part.get("text", "") for part in value
            if isinstance(part, dict) and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )
    return ""


def _model_request(
    item: Mapping[str, Any], session_id: str, turn_id: str,
) -> tuple[str, dict[str, Any]]:
    # Title-generation responses can be incomplete, but their request, scope
    # and typed OpenCode agent classification must still be verified.
    if (item.get("method") != "POST" or item.get("scheme") != "https"
        or item.get("intercepted") is not True
        or item.get("request_complete") is not True
        or item.get("request_body_truncated") is not False
        or not isinstance(item.get("exchange_id"), str)
        or not isinstance(item.get("sequence"), int)):
        raise ValueError("intercepted model request not complete")
    raw_request = item.get("request_body")
    if not isinstance(raw_request, str) or len(raw_request.encode()) > _MAX_BODY_BYTES:
        raise ValueError("missing or unbounded model request")
    body = json.loads(raw_request)
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise ValueError("model request lacks messages")
    req_headers = _headers(item.get("request_headers"))
    if (_required_header(req_headers, "x-session-id") != session_id
        or _required_header(req_headers, "x-turn-id") != turn_id
        or body.get("session_id", session_id) != session_id
        or body.get("turn_id", turn_id) != turn_id):
        raise ValueError("model traffic cannot be attributed to a session and turn")
    agent = _required_header(req_headers, "x-ats-oc-agent")
    if agent not in ("build", "title"):
        raise ValueError("unclassified or unsupported OpenCode agent model request")
    return agent, body


def _title_only_degradation(
    exchanges: Sequence[Mapping[str, Any]], *, session_id: str, turn_id: str,
    provider_host: str, diagnostics: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(diagnostics, Mapping) or set(diagnostics) != _DIAGNOSTIC_FIELDS:
        return False
    for field in ("dropped_error_count", "unattributed_error_count"):
        if type(diagnostics[field]) is not int or diagnostics[field] != 0:
            return False
    limits = diagnostics["resource_limits"]
    errors = diagnostics["retained_error_types"]
    if not isinstance(limits, (list, tuple)) or limits or not isinstance(errors, (list, tuple)):
        return False
    if any(error != "SSLEOFError" for error in errors):
        return False

    title_failures = 0
    title_ssl_errors = 0
    for item in exchanges:
        if not isinstance(item, Mapping):
            return False
        if any(type(item.get(field)) is not bool for field in (
            "request_complete", "response_complete", "request_body_truncated", "response_body_truncated",
        )):
            return False
        raw_error = item.get("error")
        if raw_error in (None, "") and (item["request_complete"] is True
            and item["response_complete"] is True
            and item["request_body_truncated"] is False
            and item["response_body_truncated"] is False):
            continue
        if item.get("host") != provider_host or item.get("path") != MODEL_PATH:
            return False
        try:
            agent, _ = _model_request(item, session_id, turn_id)
        except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
            return False
        if agent != "title" or (item["response_complete"] is True
            and item["response_body_truncated"] is False):
            return False
        if raw_error not in (None, ""):
            if not isinstance(raw_error, str) or not raw_error.startswith("SSLEOFError:"):
                return False
            title_ssl_errors += 1
        title_failures += 1
    return title_failures > 0 and title_ssl_errors == len(errors)


def _parse_exchange(
    item: Mapping[str, Any], prompt: str, session_id: str, turn_id: str,
    redactor: Callable[[Any], JsonValue],
) -> _Parsed:
    agent, body = _model_request(item, session_id, turn_id)
    if agent != "build":
        raise ValueError("background agent cannot be attributed as the main model call")
    if (item.get("response_complete") is not True
        or item.get("response_body_truncated") is not False
        or item.get("error") not in (None, "")
        or item.get("response_status") != 200):
        raise ValueError("primary model response not complete")
    raw_response = item.get("response_body")
    if not isinstance(raw_response, str) or len(raw_response.encode()) > _MAX_BODY_BYTES:
        raise ValueError("missing or unbounded primary model response")
    resp_headers = _headers(item.get("response_headers"))
    if not _has_prompt(body, prompt):
        raise ValueError("model traffic does not contain current prompt")
    request_id = _required_header(resp_headers, "x-litellm-call-id")
    if "text/event-stream" not in resp_headers.get("content-type", "").casefold():
        raise ValueError("model response lacks streaming completion framing")
    redacted_id = redactor(request_id)
    if not isinstance(redacted_id, str) or not redacted_id or len(redacted_id) > 256:
        raise ValueError("invalid redacted LiteLLM call ID")
    redacted_request = redactor(body)
    if not isinstance(redacted_request, dict) or not isinstance(redacted_request.get("messages"), list):
        raise ValueError("redaction destroyed request structure")
    text, tool_calls, response_id = _response(raw_response, resp_headers)
    # Full response body has already been validated. Redact reconstructed values
    # before any evidence is instantiated or passed to a Judge.
    response = redactor({"text": text, "tools": list(tool_calls)})
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        raise ValueError("redaction destroyed response structure")
    tools = response.get("tools")
    if not isinstance(tools, list) or any(not isinstance(tool, dict) for tool in tools):
        raise ValueError("redaction destroyed tool structure")
    redacted_response_id = redactor(response_id)
    if (not isinstance(redacted_response_id, str) or not redacted_response_id
        or len(redacted_response_id) > 256):
        raise ValueError("invalid redacted model response ID")
    return _Parsed(item, redacted_id, redacted_request, response["text"], tuple(tools), redacted_response_id)


def _response(raw: str, headers: Mapping[str, str]) -> tuple[str, tuple[dict[str, Any], ...], str]:
    if "text/event-stream" not in headers.get("content-type", ""):
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise ValueError("non-stream model response has no id")
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("model response choices ambiguous")
        choice = choices[0]
        if choice.get("finish_reason") not in ("stop", "tool_calls"):
            raise ValueError("model response has no successful finish reason")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("model response message absent")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("unexpected response content")
        return content or "", _validate_calls(message.get("tool_calls") or ()), payload["id"]

    chunks: list[dict[str, Any]] = []
    completed = False
    for frame in raw.replace("\r\n", "\n").split("\n\n"):
        if not frame.strip():
            continue
        data_lines = [line[5:].strip() for line in frame.split("\n") if line.startswith("data:")]
        if len(data_lines) != 1:
            raise ValueError("malformed or multiplexed SSE frame")
        if data_lines[0] == "[DONE]":
            completed = True
            continue
        if completed:
            raise ValueError("SSE data after end of stream")
        chunk = json.loads(data_lines[0])
        if not isinstance(chunk, dict):
            raise ValueError("SSE chunk is not an object")
        chunks.append(chunk)
    if not completed or not chunks:
        raise ValueError("SSE lacks complete framing")
    response_ids = {chunk.get("id") for chunk in chunks}
    if len(response_ids) != 1 or not isinstance((response_id := next(iter(response_ids))), str):
        raise ValueError("SSE model response ids are missing or mixed")
    text: list[str] = []
    proposals: dict[int, dict[str, str]] = {}
    finished = False
    for chunk in chunks:
        choices = chunk.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("SSE choices are ambiguous")
        choice = choices[0]
        if choice.get("index") not in (None, 0):
            raise ValueError("SSE response has multiple choices")
        finish = choice.get("finish_reason")
        if finish is not None:
            if finish not in ("stop", "tool_calls") or finished:
                raise ValueError("SSE finish state ambiguous")
            finished = True
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            raise ValueError("SSE chunk lacks delta")
        part = delta.get("content")
        if part is not None:
            if not isinstance(part, str):
                raise ValueError("SSE delta content invalid")
            text.append(part)
        for tool in delta.get("tool_calls") or ():
            if not isinstance(tool, dict) or not isinstance(tool.get("index"), int):
                raise ValueError("SSE tool proposal has no index")
            target = proposals.setdefault(tool["index"], {"id": "", "name": "", "arguments": ""})
            if isinstance(tool.get("id"), str):
                target["id"] += tool["id"]
            function = tool.get("function")
            if isinstance(function, dict):
                for source, key in (("name", "name"), ("arguments", "arguments")):
                    if isinstance(function.get(source), str):
                        target[key] += function[source]
    if not finished:
        raise ValueError("SSE response has no finish reason")
    return "".join(text), _validate_calls(tuple(proposals[index] for index in sorted(proposals))), response_id


def _validate_calls(values: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    calls: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in values:
        function = item.get("function") if isinstance(item.get("function"), Mapping) else item
        identifier = item.get("id")
        name = function.get("name") if isinstance(function, Mapping) else None
        raw_args = function.get("arguments") if isinstance(function, Mapping) else None
        if not isinstance(identifier, str) or not identifier or identifier in ids or (
            not isinstance(name, str) or not name or not isinstance(raw_args, str)
        ):
            raise ValueError("tool call ID, name or arguments are missing")
        args = json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError("tool call arguments must be an object")
        ids.add(identifier)
        calls.append({"id": identifier, "name": name, "arguments": args})
    return tuple(calls)


def _build_trace(
    parsed: Sequence[_Parsed], *, run_id: str, prompt: str, session_id: str,
    turn_id: str, redactor: Callable[[Any], JsonValue], collector_health: str,
    limitations: tuple[str, ...],
) -> tuple[AgentTrace, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contexts: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    calls: list[ModelCall] = []
    for call_index, parsed_call in enumerate(parsed):
        req = parsed_call.request
        messages: list[TraceMessage] = []
        results: list[TraceToolResult] = []
        for index, message in enumerate(req["messages"]):
            if not isinstance(message, dict) or not isinstance(message.get("role"), str):
                raise ValueError("invalid model request message")
            role = message["role"]
            content = message.get("content")
            messages.append(TraceMessage(
                message_id=f"{parsed_call.request_id}:request:{index}",
                role=role,
                content=content,
                sequence=index,
                phase=TracePhase.REQUEST,
                visibility=TraceVisibility.CURRENT
                if role == "user" and _content_text(content) == redactor(prompt)
                else TraceVisibility.HISTORY,
                source="iiis_https_interception",
            ))
            if role == "tool":
                tool_id = message.get("tool_call_id")
                if not isinstance(tool_id, str) or not tool_id:
                    raise ValueError("tool result has no call ID")
                results.append(TraceToolResult(
                    tool_call_id=tool_id, content=content,
                    stage=ToolCallStage.RETURNED,
                    sequence=call_index * 100_000 + index,
                    phase=TracePhase.REQUEST,
                    source="iiis_https_interception",
                    limitations=("Network request proves the model saw this returned result, not that a tool ran.",),
                ))
        if parsed_call.text:
            messages.append(TraceMessage(
                message_id=f"{parsed_call.response_id}:text",
                role="assistant", content=parsed_call.text,
                sequence=len(messages), phase=TracePhase.RESPONSE,
                source="iiis_https_interception",
            ))
        proposed = tuple(TraceToolCall(
            tool_call_id=tool["id"], name=tool["name"],
            arguments=tool["arguments"], stage=ToolCallStage.PROPOSED,
            sequence=call_index * 100_000 + len(req["messages"]) + idx + 1,
            phase=TracePhase.RESPONSE, source="iiis_https_interception",
        ) for idx, tool in enumerate(parsed_call.tool_calls))
        if not isinstance(req.get("tools", []), list):
            raise ValueError("model-visible tools must be an array")
        calls.append(ModelCall(
            model_call_id=parsed_call.request_id,
            sequence=call_index,
            request_id=parsed_call.request_id,
            model=req.get("model") if isinstance(req.get("model"), str) else None,
            messages=tuple(messages),
            visible_tools=tuple(req.get("tools") or ()),
            tool_calls=proposed,
            tool_results=tuple(results),
        ))
        contexts.append({
            "model_call_id": parsed_call.request_id,
            "request_id": parsed_call.request_id,
            "messages": [message.to_payload() for message in messages if message.phase is TracePhase.REQUEST],
            "visible_tools": redactor(req.get("tools") or []),
        })
        outputs.append({
            "model_call_id": parsed_call.request_id,
            "request_id": parsed_call.request_id,
            "messages": [message.to_payload() for message in messages if message.phase is TracePhase.RESPONSE],
            "tool_calls": [item.to_payload() for item in proposed],
        })
        if proposed or results:
            tools.append({
                "model_call_id": parsed_call.request_id,
                "tool_calls": [item.to_payload() for item in proposed],
                "tool_results": [item.to_payload() for item in results],
            })
    trace = AgentTrace(
        run_id=run_id, product="opencode",
        sessions=(AgentSession(session_id=session_id, turns=(AgentTurn(
            turn_id=turn_id, sequence=0,
            user_input=redactor(prompt), model_calls=tuple(calls),
            ready_state=TraceReadyState.READY,
        ),)),),
        ready_state=TraceReadyState.READY,
        collector_health=collector_health,
        limitations=limitations,
    )
    return trace, contexts, outputs, tools
