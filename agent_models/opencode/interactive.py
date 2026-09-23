"""Drive an isolated OpenCode headless session over its public HTTP/SSE API."""

from __future__ import annotations

import base64
import json
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Collection, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

import psutil

from agent_models.evidence import JsonValue
from agent_models.interaction import (
    AgentEvent,
    AgentEventType,
    ControlResult,
    EventPredicate,
    InteractiveSession,
    PermissionDecision,
    PermissionPolicy,
    TurnHandle,
)
from agent_models.result import TurnResult
from agent_models.processes import ProcessCleanupError, _remember_children, _stop_processes
from agent_models.windows_job import WindowsProcessJob


_MAX_HTTP_BYTES = 4 * 1024 * 1024
_MAX_SSE_LINE = 1024 * 1024
_MAX_EVENTS = 100_000


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _live_group_members(group_id: int) -> bool:
    """Exclude reaped/zombie children when verifying a terminated POSIX group."""
    for process in psutil.process_iter(attrs=["status"]):
        try:
            if process.info["status"] != psutil.STATUS_ZOMBIE and os.getpgid(process.pid) == group_id:
                return True
        except (ProcessLookupError, psutil.NoSuchProcess):
            continue
        except (PermissionError, psutil.AccessDenied) as error:
            raise ProcessCleanupError("Cannot inspect OpenCode process group") from error
    return False


def _stop_posix_server(process: subprocess.Popen[Any]) -> None:
    group_id = process.pid  # Popen(start_new_session=True) makes this the group ID.
    if not isinstance(group_id, int) or group_id <= 0:
        raise ProcessCleanupError("OpenCode server has no valid process group")
    descendants: set[psutil.Process] = set()
    try:
        _remember_children(psutil.Process(group_id), descendants)
    except psutil.NoSuchProcess:
        pass
    try:
        os.killpg(group_id, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError as error:
        raise ProcessCleanupError("Cannot terminate OpenCode process group") from error
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # The server may have exited while its MCP children are still alive.
    if _live_group_members(group_id):
        try:
            os.killpg(group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            raise ProcessCleanupError("Cannot kill OpenCode process group") from error
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        raise ProcessCleanupError("OpenCode server did not exit") from error
    if descendants:
        _stop_processes(descendants)
    deadline = time.monotonic() + 5
    while _live_group_members(group_id):
        if time.monotonic() >= deadline:
            raise ProcessCleanupError("OpenCode process group still has live children")
        time.sleep(0.05)


class OpenCodeInteractiveSession(InteractiveSession):
    """Own one local OpenCode server and one session with explicit permissions."""

    def __init__(
        self,
        *,
        workspace: Path,
        environment: Mapping[str, str],
        model: str,
        timeout: float,
        permission_policy: PermissionPolicy,
        allow_tools: bool = True,
        mcp_config: dict[str, JsonValue] | None = None,
        executable: str = "opencode",
        pure: bool = True,
        event_sink: Callable[[AgentEvent], None] | None = None,
        close_callback: Callable[[], None] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("interactive timeout must be positive")
        if not isinstance(permission_policy, PermissionPolicy):
            raise ValueError("permission policy must use PermissionPolicy")
        if "/" not in model or not all(model.split("/", 1)):
            raise ValueError("model must be provider/model")
        if not workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self._model = model
        self._permission_policy = permission_policy
        self._allow_tools = allow_tools
        self._event_sink = event_sink
        self._close_callback = close_callback
        self._condition = threading.Condition(threading.RLock())
        self._events: list[AgentEvent] = []
        self._next_sequence = 1
        self._active_turn: TurnHandle | None = None
        self._user_message_id: str | None = None
        self._v2_permissions: set[str] = set()
        self._seen_tool_calls: set[str] = set()
        self._seen_tool_results: set[str] = set()
        self._busy_seen = False
        self._aborted = False
        self._turn_error = ""
        self._answered: set[str] = set()
        self._sse_ready = threading.Event()
        self._collector_error: str | None = None
        self._closed = False
        self._cleanup_complete = False
        self._close_lock = threading.Lock()
        self._close_callback_called = False
        self._session_id = ""
        self._sse_response: Any = None
        self._process: subprocess.Popen[Any] | None = None
        self._job: WindowsProcessJob | None = None
        self._opener = build_opener(ProxyHandler({}))
        self._profile = tempfile.TemporaryDirectory(prefix="ats-opencode-session-")
        profile_root = Path(self._profile.name)
        env = dict(environment)
        for key, directory in (
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"),
            ("XDG_STATE_HOME", "state"),
        ):
            if key not in env:
                isolated = profile_root / directory
                isolated.mkdir()
                env[key] = str(isolated)
        if mcp_config is not None or not allow_tools:
            raw_config = env.get("OPENCODE_CONFIG_CONTENT", "{}")
            try:
                config = json.loads(raw_config)
            except json.JSONDecodeError as error:
                self._profile.cleanup()
                raise ValueError("invalid OpenCode config content") from error
            if not isinstance(config, dict):
                self._profile.cleanup()
                raise ValueError("OpenCode config content must be an object")
            if allow_tools:
                config["mcp"] = mcp_config
            else:
                config["mcp"] = {}
                configured_tools: set[str] = set()
                if isinstance(config.get("tools"), dict):
                    configured_tools.update(name for name in config["tools"] if isinstance(name, str))
                config_dir = env.get("OPENCODE_CONFIG_DIR")
                if config_dir:
                    config_file = Path(config_dir) / "opencode.json"
                    if config_file.is_file():
                        try:
                            file_config = json.loads(config_file.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError) as error:
                            self._profile.cleanup()
                            raise ValueError("invalid OpenCode profile config") from error
                        if not isinstance(file_config, dict):
                            self._profile.cleanup()
                            raise ValueError("OpenCode profile config must be an object")
                        saved_tools = file_config.get("tools")
                        if isinstance(saved_tools, dict):
                            configured_tools.update(name for name in saved_tools if isinstance(name, str))
                config["tools"] = {
                    "*": False,
                    **{name: False for name in configured_tools},
                }
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)

        # Port 0 silently selects 4096 in OpenCode 1.18.32; choose an ephemeral port.
        port = _unused_loopback_port()
        self._base_url = f"http://127.0.0.1:{port}"
        username = "opencode"
        password = uuid.uuid4().hex + uuid.uuid4().hex
        env["OPENCODE_SERVER_USERNAME"] = username
        env["OPENCODE_SERVER_PASSWORD"] = password
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._authorization = f"Basic {token}"
        try:
            if os.name == "nt":
                # Suspend until assigned to a kill-on-close Job; MCP children cannot escape.
                self._job = WindowsProcessJob()
                popen_options: dict[str, Any] = {"creationflags": 0x00000004}
            else:
                popen_options = {"start_new_session": True}
            command = (executable, "serve", *( ("--pure",) if pure else () ),
                       "--hostname", "127.0.0.1", "--port", str(port))
            self._process = subprocess.Popen(
                command,
                cwd=self.workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **popen_options,
            )
            if self._job is not None:
                self._job.attach(self._process.pid)
                psutil.Process(self._process.pid).resume()
            self._await_server()
            provider_id, model_id = model.split("/", 1)
            created = self._request(
                "POST",
                "/session",
                {
                    "model": {"id": model_id, "providerID": provider_id},
                    "permission": self._permission_rules(permission_policy, allow_tools=allow_tools),
                },
            )
            if not isinstance(created, dict) or not isinstance(created.get("id"), str):
                raise RuntimeError("OpenCode did not return a session identifier")
            self._session_id = created["id"]
            self._sse_thread = threading.Thread(
                target=self._read_events,
                name=f"opencode-events-{self._session_id}",
                daemon=True,
            )
            self._sse_thread.start()
            if not self._sse_ready.wait(min(timeout, 10.0)):
                raise TimeoutError("OpenCode event stream did not connect")
            if self._collector_error:
                raise RuntimeError(f"OpenCode event stream failed: {self._collector_error}")
            self._emit(AgentEventType.SESSION_STARTED, data={"model": model})
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _permission_rules(policy: PermissionPolicy, *, allow_tools: bool = True) -> list[dict[str, str]]:
        if not allow_tools:
            return [{"permission": "*", "pattern": "*", "action": "deny"}]
        if policy is PermissionPolicy.BYPASS:
            return [{"permission": "*", "pattern": "*", "action": "allow"}]
        rules = [{"permission": "*", "pattern": "*", "action": "ask"}]
        if policy is PermissionPolicy.ALLOW_WORKSPACE_EDITS:
            rules.append({"permission": "edit", "pattern": "*", "action": "allow"})
        return rules

    def _url(self, path: str) -> str:
        query = urlencode({"directory": str(self.workspace)})
        return f"{self._base_url}{path}?{query}"

    def _request(self, method: str, path: str, payload: JsonValue = None, *, timeout: float | None = None) -> JsonValue:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url(path),
            data=body,
            method=method,
            headers={
                "Authorization": self._authorization,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-OpenCode-Directory": str(self.workspace),
            },
        )
        try:
            with self._opener.open(request, timeout=timeout or self.timeout) as response:
                raw = response.read(_MAX_HTTP_BYTES + 1)
                if len(raw) > _MAX_HTTP_BYTES:
                    raise RuntimeError("OpenCode HTTP response exceeds size limit")
                return json.loads(raw) if raw else None
        except HTTPError as error:
            raise RuntimeError(f"OpenCode HTTP {method} {path} returned {error.code}") from None
        except (OSError, URLError) as error:
            raise RuntimeError(f"OpenCode HTTP {method} {path} failed: {type(error).__name__}") from error

    def _await_server(self) -> None:
        deadline = time.monotonic() + min(self.timeout, 15.0)
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError("OpenCode server exited during startup")
            try:
                self._request("GET", "/session/status", timeout=0.5)
                return
            except RuntimeError:
                time.sleep(0.1)
        raise TimeoutError("OpenCode server startup timed out")

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_running(self) -> bool:
        return not self._closed and self._process.poll() is None and self._collector_error is None

    @property
    def events(self) -> tuple[AgentEvent, ...]:
        with self._condition:
            return tuple(self._events)

    def _emit(
        self,
        event_type: AgentEventType,
        *,
        text: str = "",
        turn_id: str | None = None,
        request_id: str | None = None,
        data: JsonValue = None,
    ) -> AgentEvent:
        with self._condition:
            if len(self._events) >= _MAX_EVENTS:
                raise RuntimeError("OpenCode event limit exceeded")
            event = AgentEvent(
                sequence=self._next_sequence,
                event_type=event_type,
                observed_at=datetime.now(timezone.utc).isoformat(),
                monotonic_seconds=time.monotonic(),
                session_id=self._session_id or None,
                request_id=request_id,
                turn_id=turn_id,
                text=text,
                data={} if data is None else data,
            )
            self._next_sequence += 1
            self._events.append(event)
            self._condition.notify_all()
        if self._event_sink is not None:
            self._event_sink(event)
        return event

    def _read_events(self) -> None:
        try:
            request = Request(
                self._url("/event"),
                headers={
                    "Accept": "text/event-stream",
                    "Authorization": self._authorization,
                    "X-OpenCode-Directory": str(self.workspace),
                },
            )
            with self._opener.open(request, timeout=max(self.timeout, 30.0)) as response:
                if response.status != 200 or "text/event-stream" not in response.headers.get("Content-Type", ""):
                    raise RuntimeError("unexpected OpenCode event stream response")
                self._sse_response = response
                self._sse_ready.set()
                fragments: list[str] = []
                while not self._closed:
                    line = response.readline(_MAX_SSE_LINE + 1)
                    if len(line) > _MAX_SSE_LINE:
                        raise RuntimeError("OpenCode event line exceeds size limit")
                    if not line:
                        raise RuntimeError("OpenCode event stream disconnected")
                    decoded = line.decode("utf-8", "replace").rstrip("\r\n")
                    if not decoded:
                        if fragments:
                            self._on_sse(json.loads("\n".join(fragments)))
                            fragments.clear()
                        continue
                    if decoded.startswith("data:"):
                        fragments.append(decoded[5:].lstrip(" "))
        except BaseException as error:
            if not self._closed:
                with self._condition:
                    self._collector_error = f"{type(error).__name__}: {error}"
                    self._condition.notify_all()
                self._sse_ready.set()

    def _on_sse(self, item: JsonValue) -> None:
        if not isinstance(item, dict):
            raise ValueError("OpenCode event must be an object")
        kind = item.get("type")
        props = item.get("properties")
        if not isinstance(kind, str) or not isinstance(props, dict):
            raise ValueError("OpenCode event has no type or properties")
        if props.get("sessionID") != self._session_id:
            return
        with self._condition:
            active = self._active_turn
            turn_id = active.turn_id if active else None
        if kind == "session.status":
            status = props.get("status")
            if isinstance(status, dict) and status.get("type") == "busy" and active:
                self._busy_seen = True
        elif kind in {"permission.asked", "permission.v2.asked"}:
            request_id = props.get("id")
            if not isinstance(request_id, str):
                raise ValueError("OpenCode permission request lacks an id")
            if kind == "permission.v2.asked":
                self._v2_permissions.add(request_id)
            self._emit(
                AgentEventType.PERMISSION_REQUEST,
                request_id=request_id,
                turn_id=turn_id,
                data={"permission": props.get("permission", props.get("action", "")), "resources": props.get("patterns", props.get("resources", []))},
            )
            if self._permission_policy is PermissionPolicy.DENY_UNAPPROVED:
                self._reply_permission(request_id, "reject")
        elif kind == "message.part.delta" and active:
            if props.get("field") == "text":
                delta = props.get("delta")
                if isinstance(delta, str):
                    self._emit(AgentEventType.TEXT_DELTA, text=delta, turn_id=turn_id)
        elif kind == "message.part.updated" and active:
            part = props.get("part")
            if isinstance(part, dict):
                part_type = part.get("type")
                if part_type == "tool":
                    self._on_tool_part(part, turn_id=turn_id)
                    return
                event_type = {
                    "text": AgentEventType.TEXT,
                    "reasoning": AgentEventType.THINKING,
                    "tool": AgentEventType.TOOL_CALL,
                }.get(part_type)
                if event_type is not None:
                    text = part.get("text", "") if part_type == "text" else ""
                    self._emit(event_type, turn_id=turn_id, text=text if isinstance(text, str) else "", data={"part_id": part.get("id", ""), "type": part_type})
        elif kind == "session.error" and active:
            error = props.get("error")
            self._turn_error = (
                str(error.get("name") or "OpenCode session error")[:120]
                if isinstance(error, dict)
                else "OpenCode session error"
            )
            self._complete_active(error=self._turn_error)
        elif kind == "session.idle" and active and self._busy_seen:
            self._complete_active(error=self._turn_error or ("OpenCode turn was cancelled" if self._aborted else ""))

    def _on_tool_part(self, part: dict[str, JsonValue], *, turn_id: str) -> None:
        call_id = part.get("callID") or part.get("id")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("OpenCode tool event has no call identifier")
        state = part.get("state")
        status = state.get("status") if isinstance(state, dict) else "unknown"
        data: dict[str, JsonValue] = {
            "call_id": call_id,
            "tool": str(part.get("tool") or ""),
            "status": str(status),
        }
        if call_id not in self._seen_tool_calls:
            self._seen_tool_calls.add(call_id)
            self._emit(AgentEventType.TOOL_CALL, turn_id=turn_id, data=data)
        if status in {"completed", "error"} and call_id not in self._seen_tool_results:
            self._seen_tool_results.add(call_id)
            self._emit(AgentEventType.TOOL_RESULT, turn_id=turn_id, data=data)

    def _complete_active(self, *, error: str = "") -> None:
        with self._condition:
            active = self._active_turn
            if active is None:
                return
            self._active_turn = None
            self._emit(
                AgentEventType.TURN_COMPLETED,
                turn_id=active.turn_id,
                data={"error": error, "user_message_id": self._user_message_id},
            )

    def send_input(self, prompt: str) -> TurnHandle:
        if not prompt.strip():
            raise ValueError("interactive prompt must be nonempty")
        with self._condition:
            self._ensure_healthy()
            if self._active_turn is not None:
                raise RuntimeError("wait for the active turn before sending another input")
            handle = TurnHandle(uuid.uuid4().hex, prompt, self._next_sequence - 1, time.monotonic())
            message_id = "msg_" + uuid.uuid4().hex
            self._active_turn = handle
            self._busy_seen = False
            self._aborted = False
            self._turn_error = ""
            self._user_message_id = message_id
            self._emit(AgentEventType.USER_INPUT, text=prompt, turn_id=handle.turn_id)
        try:
            provider_id, model_id = self._model.split("/", 1)
            self._request(
                "POST",
                f"/session/{quote(self._session_id, safe='')}/prompt_async",
                {"messageID": message_id, "model": {"providerID": provider_id, "modelID": model_id}, "parts": [{"type": "text", "text": prompt}]},
            )
        except BaseException:
            with self._condition:
                if self._active_turn is handle:
                    self._active_turn = None
            raise
        return handle

    def _ensure_healthy(self) -> None:
        if self._closed or self._process.poll() is not None:
            raise RuntimeError("OpenCode interactive session is closed")
        if self._collector_error:
            raise RuntimeError(f"OpenCode event collection failed: {self._collector_error}")

    def wait_for_event(
        self,
        event_types: AgentEventType | Collection[AgentEventType],
        *,
        timeout: float,
        after_sequence: int = 0,
        predicate: EventPredicate | None = None,
    ) -> AgentEvent:
        if timeout <= 0:
            raise ValueError("event timeout must be positive")
        accepted = frozenset((event_types,)) if isinstance(event_types, AgentEventType) else frozenset(event_types)
        if not accepted or not all(isinstance(item, AgentEventType) for item in accepted):
            raise ValueError("event_types must be nonempty AgentEventType values")
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                for event in self._events:
                    if event.sequence > after_sequence and event.event_type in accepted and (predicate is None or predicate(event)):
                        return event
                self._ensure_healthy()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for OpenCode event")
                self._condition.wait(remaining)

    def wait_for_completion(self, turn: TurnHandle, *, timeout: float | None = None) -> TurnResult:
        terminal = self.wait_for_event(
            AgentEventType.TURN_COMPLETED,
            timeout=self.timeout if timeout is None else timeout,
            after_sequence=turn.after_sequence,
            predicate=lambda event: event.turn_id == turn.turn_id,
        )
        detail = terminal.data if isinstance(terminal.data, dict) else {}
        error = str(detail.get("error") or "")
        user_message_id = detail.get("user_message_id")
        messages = self._request("GET", f"/session/{quote(self._session_id, safe='')}/message")
        if not isinstance(messages, list):
            raise RuntimeError("OpenCode session messages response is invalid")
        reply: list[str] = []
        saw_user = False
        saw_assistant = False
        for message in messages:
            if not isinstance(message, dict):
                continue
            info = message.get("info")
            if not isinstance(info, dict):
                continue
            if info.get("id") == user_message_id and info.get("role") == "user":
                saw_user = True
                continue
            if not saw_user:
                continue
            if info.get("role") == "user":
                break
            if info.get("role") != "assistant":
                continue
            saw_assistant = True
            if isinstance(info.get("error"), dict):
                error = str(info["error"].get("name") or error or "OpenCode assistant error")[:120]
            for part in message.get("parts", []):
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    reply.append(part["text"])
        if not saw_user and not error:
            error = "OpenCode response missing the input message"
        if not saw_assistant and not error:
            error = "OpenCode response missing the assistant message"
        response_text = "".join(reply)
        return TurnResult(
            response=response_text,
            raw_output=response_text,
            stderr=error,
            returncode=0 if not error else 1,
            completed=not error,
            duration_seconds=max(0.0, terminal.monotonic_seconds - turn.sent_at_monotonic),
            session_id=self._session_id,
        )

    def _reply_permission(self, request_id: str, reply: str) -> None:
        with self._condition:
            if request_id in self._answered:
                raise ValueError("OpenCode permission request has already been answered")
            if request_id in self._v2_permissions:
                self._request(
                    "POST", f"/api/session/{quote(self._session_id, safe='')}/permission/{quote(request_id, safe='')}/reply", {"reply": reply}
                )
            else:
                self._request("POST", f"/permission/{quote(request_id, safe='')}/reply", {"reply": reply})
            self._answered.add(request_id)
        self._emit(AgentEventType.PERMISSION_DECISION, request_id=request_id, turn_id=self._active_turn.turn_id if self._active_turn else None, data={"decision": reply})

    def respond_to_confirmation(
        self,
        event: AgentEvent,
        decision: PermissionDecision,
        *,
        reason: str,
        updated_input: dict[str, JsonValue] | None = None,
    ) -> None:
        if event.event_type is not AgentEventType.PERMISSION_REQUEST or not event.request_id:
            raise ValueError("expected an OpenCode permission request")
        if event.session_id != self._session_id:
            raise ValueError("permission request belongs to a different session")
        if not reason.strip():
            raise ValueError("permission decision reason is required")
        if updated_input is not None:
            raise ValueError("OpenCode permission reply cannot rewrite tool input")
        if not isinstance(decision, PermissionDecision):
            raise ValueError("invalid permission decision")
        reply = "once" if decision is PermissionDecision.ALLOW else "reject"
        self._reply_permission(event.request_id, reply)
        if decision is PermissionDecision.CANCEL:
            self.interrupt_task(reason=reason)

    def steer(self, text: str, *, timeout: float | None = None, expected_request_id: str | None = None) -> ControlResult:
        return ControlResult(uuid.uuid4().hex, False, error="steering is unavailable on OpenCode v1 session API")

    def interrupt_task(self, *, reason: str, timeout: float | None = None) -> ControlResult:
        if not reason.strip():
            raise ValueError("interrupt reason is required")
        request_id = uuid.uuid4().hex
        with self._condition:
            active = self._active_turn
            if active is None:
                return ControlResult(request_id, False, error="idle")
            self._aborted = True
            # The SSE idle event may race ahead of the HTTP abort response.
            self._emit(AgentEventType.CONTROL_REQUEST, request_id=request_id, turn_id=active.turn_id, data={"action": "abort"})
        response = self._request("POST", f"/session/{quote(self._session_id, safe='')}/abort", timeout=timeout)
        accepted = response is True
        if not accepted:
            with self._condition:
                self._aborted = False
        self._emit(AgentEventType.CONTROL_RESPONSE, request_id=request_id, turn_id=active.turn_id, data={"success": accepted})
        return ControlResult(request_id, accepted, data={"interrupted": accepted}, error="" if accepted else "OpenCode did not accept abort")

    def close(self) -> None:
        with self._close_lock:
            if self._cleanup_complete:
                return
            with self._condition:
                self._closed = True
                self._condition.notify_all()
            process = self._process
            if self._job is not None:
                try:
                    self._job.__exit__(None, None, None)
                finally:
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                if process is not None:
                    process.wait(timeout=5)
            elif process is not None:
                _stop_posix_server(process)
            try:
                self._profile.cleanup()
            finally:
                self._cleanup_complete = True
                if not self._close_callback_called:
                    self._close_callback_called = True
                    if self._close_callback is not None:
                        self._close_callback()
