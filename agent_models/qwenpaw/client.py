"""Talk to one QwenPaw instance over its public loopback REST and SSE console API."""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

from agent_models.interaction import PermissionPolicy

_MAX_SSE_EVENT_BYTES = 4 * 1024 * 1024
_MAX_HTTP_BYTES = 4 * 1024 * 1024
_TERMINAL_STATUSES = frozenset({"completed", "failed", "canceled", "cancelled"})
_CALL_TYPES = frozenset({"plugin_call", "function_call", "mcp_tool_call"})
_OUTPUT_TYPES = frozenset({"plugin_call_output", "function_call_output", "mcp_tool_call_output"})

# Policy-layer tool names from QwenPaw 2.2.1's governance registry.
READ_ONLY_TOOLS = frozenset({"Read", "Glob", "Grep", "AstSearch", "ViewImage", "ViewVideo"})
WORKSPACE_WRITE_TOOLS = frozenset({"Write", "Edit", "Append"})
SIDE_EFFECT_FREE_INTERNAL_TOOLS = frozenset({
    "GetCurrentTime", "GetTokenUsage", "MemorySearch", "RecallHistory", "ListAgents", "CheckAgentTask",
})
MOCK_MCP_CLIENT_KEY = "ats_mock"


class QwenPawApiError(RuntimeError):
    """A QwenPaw REST call failed; the message never contains request bodies."""

    def __init__(self, method: str, path: str, status: int | None, detail: str) -> None:
        super().__init__(f"QwenPaw {method} {path} failed ({status}): {detail[:300]}")
        self.status = status


def iter_sse_events(lines: Iterable[bytes]) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a ``text/event-stream`` byte line iterator."""
    data: list[str] = []
    size = 0
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if line == "":
            if data:
                text = "\n".join(data)
                data.clear()
                size = 0
                if text == "[DONE]":
                    continue
                event = json.loads(text)
                if not isinstance(event, dict):
                    raise ValueError("SSE event must be a JSON object")
                yield event
            continue
        if line.startswith("data:"):
            value = line[5:]
            value = value[1:] if value.startswith(" ") else value
            size += len(value)
            if size > _MAX_SSE_EVENT_BYTES:
                raise ValueError("SSE event exceeds size limit")
            data.append(value)
        # Comments and event/id/retry fields carry no product data.
    if data:
        raise ValueError("SSE stream ended inside an event")


@dataclass(slots=True)
class TurnTranscript:
    """Normalized view of one console turn's SSE stream."""

    events: list[dict[str, Any]] = field(default_factory=list)
    terminal: dict[str, Any] | None = None

    def add(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        if event.get("object") == "response" and event.get("status") in _TERMINAL_STATUSES:
            self.terminal = event

    def _messages(self) -> list[tuple[str, str, list[dict[str, Any]]]]:
        """Return (msg_id, type, content parts) in first-seen order, completed snapshots preferred."""
        order: list[str] = []
        types: dict[str, str] = {}
        completed: dict[str, list[dict[str, Any]]] = {}
        deltas: dict[str, list[dict[str, Any]]] = {}
        for event in self.events:
            kind = event.get("object")
            if kind == "message" and isinstance(event.get("id"), str):
                msg_id = event["id"]
                if msg_id not in types:
                    order.append(msg_id)
                types[msg_id] = str(event.get("type") or "")
                if event.get("status") == "completed" and isinstance(event.get("content"), list):
                    completed[msg_id] = [part for part in event["content"] if isinstance(part, dict)]
            elif kind == "content" and isinstance(event.get("msg_id"), str):
                deltas.setdefault(event["msg_id"], []).append(event)
        return [(msg_id, types[msg_id], completed.get(msg_id, deltas.get(msg_id, []))) for msg_id in order]

    @property
    def response_text(self) -> str:
        """User-visible assistant text; reasoning, tool and heartbeat messages are excluded."""
        texts = []
        for _msg_id, msg_type, parts in self._messages():
            if msg_type != "message":
                continue
            text = "".join(str(part.get("text") or "") for part in parts if part.get("type") == "text")
            if text.strip():
                texts.append(text)
        return "\n\n".join(texts)

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        """Pair tool calls with their outputs by ``call_id``."""
        calls: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for _msg_id, msg_type, parts in self._messages():
            if msg_type not in _CALL_TYPES | _OUTPUT_TYPES:
                continue
            for part in parts:
                data = part.get("data")
                if not isinstance(data, dict) or not isinstance(data.get("call_id"), str):
                    continue
                entry = calls.setdefault(data["call_id"], {"call_id": data["call_id"]})
                if data["call_id"] not in order:
                    order.append(data["call_id"])
                entry["name"] = data.get("name", entry.get("name"))
                if msg_type in _CALL_TYPES:
                    entry["arguments"] = data.get("arguments")
                else:
                    entry["output"] = data.get("output")
                    entry["state"] = data.get("state")
        return [calls[call_id] for call_id in order]

    @property
    def status(self) -> str | None:
        return None if self.terminal is None else str(self.terminal.get("status"))

    @property
    def error(self) -> str:
        error = None if self.terminal is None else self.terminal.get("error")
        if isinstance(error, dict):
            return f"{error.get('code', '')}: {error.get('message', '')}".strip(": ")
        return "" if error is None else str(error)

    def structural_events(self) -> list[dict[str, Any]]:
        """Events without per-token deltas, bounded for archiving."""
        return [event for event in self.events if not (event.get("object") == "content" and event.get("delta"))]


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    request_id: str
    tool_name: str
    tool_source: str
    target: str
    approve: bool
    rule: str


def decide_approval(
    item: dict[str, Any],
    *,
    policy: PermissionPolicy,
    allow_tools: bool,
    project_dir: Path,
    mock_configured: bool,
) -> ApprovalDecision:
    """Answer one pending QwenPaw approval for an unattended turn.

    Mirrors the framework's other drivers: reads and evaluator mock tools are
    allowed, workspace edits only when the policy says so, everything else is
    denied. ``ASK`` cannot be answered without an interactive handler.
    """
    if policy is PermissionPolicy.ASK:
        raise ValueError("one-shot QwenPaw turns cannot answer interactive permission requests")
    tool_name = str(item.get("tool_name") or "")
    source = str(item.get("tool_source") or "")
    target = str(item.get("exact_target") or "")
    request_id = str(item.get("request_id") or "")

    def result(approve: bool, rule: str) -> ApprovalDecision:
        return ApprovalDecision(request_id, tool_name, source, target, approve, rule)

    if not allow_tools:
        return result(False, "tools_disabled")
    if policy is PermissionPolicy.BYPASS:
        return result(True, "bypass")
    if source == f"mcp:{MOCK_MCP_CLIENT_KEY}" or tool_name == f"driver:mcp:{MOCK_MCP_CLIENT_KEY}":
        return result(mock_configured, "evaluator_mock_tool" if mock_configured else "mock_not_configured")
    if tool_name in READ_ONLY_TOOLS:
        return result(True, "read_only")
    if tool_name in SIDE_EFFECT_FREE_INTERNAL_TOOLS:
        return result(True, "side_effect_free_internal")
    if tool_name in WORKSPACE_WRITE_TOOLS:
        if policy is not PermissionPolicy.ALLOW_WORKSPACE_EDITS:
            return result(False, "edit_not_permitted")
        # When exact_target is absent we cannot verify the path, but the policy
        # explicitly permits workspace edits — approve rather than deny.
        if not target or _inside(target, project_dir):
            return result(True, "workspace_edit")
        return result(False, "edit_outside_workspace")
    return result(False, "not_permitted")


def _inside(target: str, root: Path) -> bool:
    if not target:
        return False
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    session_id: str
    transcript: TurnTranscript
    decisions: tuple[ApprovalDecision, ...]
    duration_seconds: float
    timed_out: bool = False
    stopped: bool | None = None
    transport_error: str = ""


class QwenPawClient:
    """Minimal console API client; loopback only and never through an HTTP proxy."""

    def __init__(self, base_url: str, *, agent_id: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._opener = build_opener(ProxyHandler({}))

    def _request(self, method: str, path: str, *, timeout: float = 30.0, **kwargs: Any) -> Any:
        body = kwargs.get("body")
        data = None if "body" not in kwargs else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + path, data=data, method=method, headers={
            "Content-Type": "application/json", "Accept": "application/json", "X-Agent-Id": self.agent_id,
        })
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(_MAX_HTTP_BYTES + 1)
        except HTTPError as error:
            raise QwenPawApiError(method, path, error.code, error.read(2000).decode("utf-8", "replace")) from None
        except (URLError, TimeoutError, OSError) as error:
            raise QwenPawApiError(method, path, None, type(error).__name__) from None
        if len(raw) > _MAX_HTTP_BYTES:
            raise QwenPawApiError(method, path, None, "response exceeds size limit")
        return json.loads(raw) if raw else None

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def put(self, path: str, body: Any, **kwargs: Any) -> Any:
        return self._request("PUT", path, body=body, **kwargs)

    def post(self, path: str, body: Any = None, **kwargs: Any) -> Any:
        return self._request("POST", path, body={} if body is None else body, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

    def version(self, *, timeout: float = 5.0) -> str:
        payload = self.get("/api/version", timeout=timeout)
        return str(payload.get("version")) if isinstance(payload, dict) else ""

    def chat_status(self, session_id: str) -> str | None:
        chats = self.get("/api/chats")
        for chat in chats if isinstance(chats, list) else []:
            if isinstance(chat, dict) and chat.get("session_id") == session_id:
                return str(chat.get("status"))
        return None

    def wait_idle(self, session_id: str, *, timeout: float) -> bool:
        """A completed SSE stream may precede the chat leaving ``running``."""
        deadline = time.monotonic() + timeout
        while True:
            status = self.chat_status(session_id)
            if status in (None, "idle"):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.5)

    def stop(self, session_id: str) -> bool:
        payload = self.post("/api/console/chat/stop?chat_id=" + quote(session_id, safe=""))
        return bool(isinstance(payload, dict) and payload.get("stopped"))

    def pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        payload = self.get("/api/approval/list?session_id=" + quote(session_id, safe=""))
        items = payload.get("pending_approvals") if isinstance(payload, dict) else None
        return [item for item in items or [] if isinstance(item, dict) and item.get("session_id") == session_id]

    def answer_approval(self, decision: ApprovalDecision, session_id: str) -> None:
        if decision.approve:
            self.post("/api/approval/approve",
                      {"request_id": decision.request_id, "session_id": session_id, "scope": "exact"})
        else:
            self.post("/api/approval/deny", {"request_id": decision.request_id, "session_id": session_id,
                                             "reason": f"Denied by test permission policy ({decision.rule})"})

    def run_turn(
        self,
        prompt: str,
        *,
        session_id: str,
        user_id: str,
        timeout: float,
        decide: Callable[[dict[str, Any]], ApprovalDecision],
        on_decision: Callable[[ApprovalDecision], None] | None = None,
        poll_interval: float = 1.0,
    ) -> TurnOutcome:
        """Stream one turn while answering its approvals; stop it at the deadline."""
        started = time.monotonic()
        deadline = started + timeout
        if not self.wait_idle(session_id, timeout=min(30.0, timeout)):
            return TurnOutcome(session_id, TurnTranscript(), (), time.monotonic() - started,
                               transport_error="session still running from a previous turn")
        body = {"input": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "session_id": session_id, "user_id": user_id, "channel": "console"}
        request = Request(self.base_url + "/api/console/chat",
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json", "Accept": "text/event-stream",
                                   "X-Agent-Id": self.agent_id})
        transcript = TurnTranscript()
        events: queue.Queue[tuple[str, Any]] = queue.Queue()

        def read() -> None:
            try:
                # The read timeout bounds a silent socket; QwenPaw sends heartbeats while waiting.
                with self._opener.open(request, timeout=90) as response:
                    for event in iter_sse_events(response):
                        events.put(("event", event))
                        if (event.get("object") == "response"
                                and event.get("status") in _TERMINAL_STATUSES):
                            break
                events.put(("end", None))
            except HTTPError as error:
                events.put(("error", f"HTTP {error.code}: {error.read(500).decode('utf-8', 'replace')}"))
            except (URLError, TimeoutError, OSError, ValueError) as error:
                events.put(("error", f"{type(error).__name__}: {error}"))

        reader = threading.Thread(target=read, name=f"qwenpaw-sse-{uuid.uuid4().hex[:8]}", daemon=True)
        reader.start()
        decisions: list[ApprovalDecision] = []
        answered: set[str] = set()
        transport_error = ""
        finished = False
        next_poll = time.monotonic()
        while not finished:
            now = time.monotonic()
            if now >= deadline:
                break
            try:
                kind, value = events.get(timeout=max(0.05, min(next_poll, deadline) - now))
            except queue.Empty:
                kind, value = "tick", None
            if kind == "event":
                transcript.add(value)
            elif kind == "end":
                finished = True
            elif kind == "error":
                transport_error = value
                finished = True
            if time.monotonic() >= next_poll and not finished:
                next_poll = time.monotonic() + poll_interval
                for item in self.pending_approvals(session_id):
                    request_id = str(item.get("request_id") or "")
                    if not request_id or request_id in answered:
                        continue
                    answered.add(request_id)
                    decision = decide(item)
                    self.answer_approval(decision, session_id)
                    decisions.append(decision)
                    if on_decision is not None:
                        on_decision(decision)
        timed_out = not finished
        stopped: bool | None = None
        if timed_out:
            stopped = self.stop(session_id)
            reader.join(10)
            while not events.empty():
                kind, value = events.get_nowait()
                if kind == "event":
                    transcript.add(value)
        if finished and not transport_error:
            self.wait_idle(session_id, timeout=30.0)
        return TurnOutcome(session_id, transcript, tuple(decisions), time.monotonic() - started,
                           timed_out=timed_out, stopped=stopped, transport_error=transport_error)
