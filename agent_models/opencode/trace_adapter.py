"""Project OpenCode's public JSON events into bounded, partial runtime evidence."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    EvidenceStatus,
    JsonValue,
)
from evidence_collectors.trace import (
    AgentSession,
    AgentTrace,
    AgentTurn,
    TraceReadyState,
    TraceRuntimeEffect,
)


_MAX_EVENTS = 4_096
_MAX_BYTES = 2 * 1024 * 1024
_MAX_FIELD_BYTES = 4_096
_PUBLIC_TYPES = frozenset({"step_start", "step_finish", "text", "tool_use", "error"})
_LIMITS = (
    "The public OpenCode CLI event stream does not include complete model requests, "
    "model-visible context, or all hidden internal operations.",
    "CLI tool events report client runtime state; independently observed tool I/O is "
    "required to prove an external side effect or absence of other tool calls.",
    "Evidence source time is the projection time, not the time each CLI event occurred.",
)


class OpenCodeTraceAdapter:
    """Consume one CLI invocation's JSONL, never events from previous turns.

    ``raw_events`` must be the output of one ``opencode run --format json``
    invocation, not a concatenated session log. ``redactor`` should be the
    EvidenceLedger's redact method; without it, content and tool arguments are
    omitted. The projected trace is *always partial* and deliberately has no
    model calls. In particular this adapter never emits reconstructed_agent_trace.
    """

    def capture(
        self,
        request: EvidenceRequest,
        *,
        raw_events: str | Sequence[Mapping[str, Any]],
        run_id: str,
        redactor: Callable[[Any], JsonValue] | None = None,
        turn_id: str | None = None,
        product_version: str | None = None,
        started_at_ms: int | None = None,
        ended_at_ms: int | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        """Return runtime observations and an explicitly partial AgentTrace.

        Optional millisecond bounds are enforced against the CLI's event
        ``timestamp``; absent or out-of-window timestamps fail closed.
        """

        if request.phase is not EvidencePhase.AFTER:
            return ()
        if not run_id or (request.context and request.context.run_id != run_id):
            raise ValueError("evidence run_id must match the request context")
        if (started_at_ms is None) != (ended_at_ms is None) or (
            started_at_ms is not None
            and (started_at_ms < 0 or ended_at_ms < started_at_ms)
        ):
            raise ValueError("valid start and end bounds must be provided together")

        observed_at = datetime.now(timezone.utc).isoformat()
        source = EvidenceSource(
            provider="opencode_cli",
            channel="public_json_cli",
            authority=EvidenceAuthority.PRODUCT_RUNTIME,
            product="opencode",
            product_version=product_version,
            observed_at=observed_at,
        )
        try:
            events = _read_bounded(raw_events)
            session_ids = {
                sid for event in events
                if (sid := _session_id(event)) is not None
            }
            if not events or len(session_ids) != 1 or (
                request.session_id is not None
                and session_ids != {request.session_id}
            ):
                raise ValueError("CLI events have no unique matching session")
            if any(_session_id(event) is None for event in events):
                raise ValueError("CLI event lacks a session identifier")
            if started_at_ms is not None and any(
                not _in_window(event, started_at_ms, ended_at_ms)
                for event in events
            ):
                raise ValueError("CLI event missing timestamp or outside turn window")
        except (TypeError, ValueError) as error:
            # Never put untrusted raw CLI data in a collection diagnostic.
            return (EvidenceRecord(
                "agent_runtime_events", "collection_diagnostic", request.phase,
                {"events": []}, status=EvidenceStatus.UNVERIFIED,
                source=source, correlation=EvidenceCorrelation(run_id=run_id),
                limitations=(*_LIMITS, f"Event window rejected: {type(error).__name__}"),
            ),)

        session_id = next(iter(session_ids))
        public_session_id = _safe_public_text(session_id, redactor)
        selected_turn_id = turn_id or (
            f"{request.sample_id}:{request.prompt_id}:repeat-{request.repeat_index}"
        )
        selected_turn_id = _safe_public_text(selected_turn_id, redactor)
        normalized: list[dict[str, JsonValue]] = []
        effects: list[TraceRuntimeEffect] = []
        tool_ids: set[str] = set()
        for sequence, event in enumerate(events):
            kind = event.get("type")
            if kind not in _PUBLIC_TYPES:
                continue
            part = event.get("part")
            part = part if isinstance(part, Mapping) else {}
            item: dict[str, JsonValue] = {"sequence": sequence, "kind": kind}
            stamp = event.get("timestamp")
            timestamp = _iso_time(stamp)
            if timestamp is not None:
                item["observed_at"] = timestamp
            message_id = _safe_id(part.get("messageID"))
            if message_id is not None:
                item["message_id"] = _safe_public_text(message_id, redactor)
            if kind == "tool_use":
                tool = part.get("tool")
                call_id = _safe_id(part.get("callID"))
                state = part.get("state")
                status = state.get("status") if isinstance(state, Mapping) else None
                if not (
                    isinstance(tool, str) and tool and call_id
                    and status in {"pending", "running", "completed", "error"}
                ):
                    continue
                public_tool = _safe_public_text(tool[:256], redactor)
                public_call_id = _safe_public_text(call_id, redactor)
                item.update({"tool": public_tool, "call_id": public_call_id, "status": status})
                tool_ids.add(public_call_id)
                if redactor is not None and isinstance(state, Mapping):
                    for key in ("input", "output", "error"):
                        if key in state:
                            value = _redacted_field(state[key], redactor)
                            if value is not None:
                                item[key] = value
                if status in {"completed", "error"}:
                    effects.append(TraceRuntimeEffect(
                        effect_id=f"tool-event-{sequence}",
                        effect_type="cli_tool_state",
                        action="tool_use",
                        target=public_tool,
                        tool_call_id=public_call_id,
                        outcome=status,
                        sequence=sequence,
                        details={"status": status, "tool": public_tool},
                        ready_state=TraceReadyState.PARTIAL,
                        source="opencode_public_cli",
                        observed_at=timestamp,
                        limitations=("A CLI tool state does not prove a remote side effect.",),
                    ))
            elif kind == "text":
                text = part.get("text")
                if isinstance(text, str):
                    item["text_present"] = bool(text)
                    if redactor is not None:
                        value = _redacted_field(text, redactor)
                        if value is not None:
                            item["text"] = value
            elif kind == "step_finish":
                reason = part.get("reason")
                if isinstance(reason, str):
                    item["reason"] = _safe_public_text(reason[:128], redactor)
            elif kind == "error":
                error = event.get("error")
                if isinstance(error, Mapping):
                    name = error.get("name")
                    if isinstance(name, str):
                        item["error_type"] = _safe_public_text(name[:128], redactor)
            normalized.append(item)

        correlation = EvidenceCorrelation(
            run_id=run_id,
            session_ids=(public_session_id,),
            turn_ids=(selected_turn_id,),
            tool_use_ids=tuple(sorted(tool_ids)),
        )
        trace = AgentTrace(
            run_id=run_id, product="opencode",
            sessions=(AgentSession(
                session_id=public_session_id,
                turns=(AgentTurn(
                    turn_id=selected_turn_id,
                    sequence=0,
                    user_input="[CLI input omitted]",
                    runtime_effects=tuple(effects),
                    ready_state=TraceReadyState.PARTIAL,
                    limitations=_LIMITS,
                ),),
                ready_state=TraceReadyState.PARTIAL,
                limitations=_LIMITS,
            ),),
            ready_state=TraceReadyState.PARTIAL,
            limitations=_LIMITS,
        )
        return (
            EvidenceRecord(
                "agent_runtime_events", "runtime_evidence", request.phase,
                {"events": normalized, "turn_scope": "single_cli_invocation"},
                status=EvidenceStatus.AVAILABLE if normalized else EvidenceStatus.MISSING,
                source=source, correlation=correlation,
                proves=("OpenCode reported these events on this CLI invocation",)
                if normalized else (),
                limitations=_LIMITS,
            ),
            EvidenceRecord(
                "opencode_public_trace", "agent_trace_evidence", request.phase,
                trace.to_payload(), status=EvidenceStatus.AVAILABLE if normalized else EvidenceStatus.MISSING,
                source=source, correlation=correlation,
                proves=("Observed OpenCode CLI tool terminal states, when present",)
                if effects else (),
                limitations=_LIMITS,
            ),
        )


def _safe_id(value: Any) -> str | None:
    return value[:256] if isinstance(value, str) and value and len(value) <= 256 else None


def _safe_public_text(value: str, redactor: Callable[[Any], JsonValue] | None) -> str:
    if redactor is None:
        return value
    redacted = redactor(value)
    return redacted if isinstance(redacted, str) and redacted else "[REDACTED]"


def _session_id(event: Mapping[str, Any]) -> str | None:
    sid = _safe_id(event.get("sessionID"))
    part = event.get("part")
    nested = _safe_id(part.get("sessionID")) if isinstance(part, Mapping) else None
    if sid is not None and nested is not None and sid != nested:
        return None
    return sid or nested


def _iso_time(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _in_window(event: Mapping[str, Any], start: int, end: int) -> bool:
    timestamp = event.get("timestamp")
    return (isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
            and start <= timestamp <= end)


def _redacted_field(value: Any, redactor: Callable[[Any], JsonValue]) -> JsonValue | None:
    try:
        result = redactor(value)
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= _MAX_FIELD_BYTES:
            return result
    except (TypeError, ValueError, RecursionError):
        return None
    return None


def _read_bounded(raw: str | Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("event stream exceeds size limit")
        lines = raw.splitlines()
        if len(lines) > _MAX_EVENTS:
            raise ValueError("event stream exceeds event limit")
        try:
            events = [json.loads(line) for line in lines if line.strip()]
        except json.JSONDecodeError as error:
            raise ValueError("malformed JSONL") from error
    else:
        if len(raw) > _MAX_EVENTS:
            raise ValueError("event stream exceeds event limit")
        events = list(raw)
        try:
            if len(json.dumps(events, ensure_ascii=False).encode("utf-8")) > _MAX_BYTES:
                raise ValueError("event stream exceeds size limit")
        except (TypeError, ValueError, RecursionError) as error:
            raise ValueError("invalid event stream") from error
    if any(not isinstance(event, Mapping) for event in events):
        raise ValueError("event must be an object")
    return events
