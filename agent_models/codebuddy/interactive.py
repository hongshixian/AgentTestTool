"""Persistent CodeBuddy STDIO driver using the public stream-json protocol."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from agent_models.evidence import JsonValue
from agent_models.interaction import (
    AgentEvent,
    AgentEventType,
    ControlResult,
    EventPredicate,
    InteractiveSession,
    PermissionDecision,
    TurnHandle,
)
from agent_models.result import TurnResult


EventSink = Callable[[AgentEvent], None]
CloseCallback = Callable[[], None]


class CodeBuddyInteractiveSession(InteractiveSession):
    """Own one long-lived CodeBuddy process and normalize its NDJSON stream."""

    def __init__(
        self,
        *,
        command: Sequence[str],
        workspace: Path,
        environment: Mapping[str, str],
        session_id: str,
        default_timeout: float = 90.0,
        close_timeout: float = 5.0,
        max_events: int = 100_000,
        max_line_chars: int = 1_048_576,
        event_sink: EventSink | None = None,
        close_callback: CloseCallback | None = None,
        initialize: bool = True,
    ) -> None:
        if (
            not command
            or not isinstance(command[0], str)
            or not command[0]
            or not all(isinstance(item, str) for item in command)
        ):
            raise ValueError(
                "interactive command must have an executable and string arguments"
            )
        if not session_id:
            raise ValueError("session_id must be nonempty")
        if default_timeout <= 0 or close_timeout <= 0:
            raise ValueError("interactive timeouts must be positive")
        if max_events <= 0 or max_line_chars <= 0:
            raise ValueError("interactive stream limits must be positive")

        self._session_id = session_id
        self.default_timeout = default_timeout
        self.close_timeout = close_timeout
        self.max_events = max_events
        self.max_line_chars = max_line_chars
        self._event_sink = event_sink
        self._close_callback = close_callback
        self._condition = threading.Condition(threading.RLock())
        self._write_lock = threading.Lock()
        self._events: list[AgentEvent] = []
        self._raw_stdout: list[tuple[int, str]] = []
        self._stderr: list[tuple[int, str]] = []
        self._next_sequence = 1
        self._active_turn: TurnHandle | None = None
        self._answered_permission_requests: set[str] = set()
        self._collector_error: BaseException | None = None
        self._closed = False
        self._close_callback_called = False

        popen_options: dict[str, Any] = {}
        if os.name == "nt":
            popen_options["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            popen_options["start_new_session"] = True
        self._process = subprocess.Popen(
            tuple(command),
            cwd=workspace,
            env=dict(environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **popen_options,
        )
        if self._process.stdin is None or self._process.stdout is None:
            self._process.kill()
            raise RuntimeError("CodeBuddy interactive process has no STDIO pipes")

        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name=f"codebuddy-stdout-{session_id}",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name=f"codebuddy-stderr-{session_id}",
            daemon=True,
        )
        self._wait_thread = threading.Thread(
            target=self._wait_for_exit,
            name=f"codebuddy-exit-{session_id}",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        self._wait_thread.start()

        try:
            if initialize:
                result = self._send_control(
                    "initialize",
                    {
                        "capabilities": {"askUserQuestion": True},
                        "hasPrompt": True,
                    },
                    timeout=min(default_timeout, 30.0),
                )
                if not result.success:
                    raise RuntimeError(
                        f"CodeBuddy stream-json initialization failed: {result.error}"
                    )
        except BaseException:
            self._close_callback = None
            self.close()
            raise

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_running(self) -> bool:
        return not self._closed and self._process.poll() is None

    @property
    def events(self) -> tuple[AgentEvent, ...]:
        with self._condition:
            return tuple(self._events)

    def send_input(self, prompt: str) -> TurnHandle:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("interactive prompt must be nonempty")
        with self._condition:
            self._ensure_healthy()
            if self._active_turn is not None:
                raise RuntimeError("wait for the active turn before sending another input")
            handle = TurnHandle(
                turn_id=uuid.uuid4().hex,
                prompt=prompt,
                after_sequence=self._next_sequence - 1,
                sent_at_monotonic=time.monotonic(),
            )
            self._active_turn = handle
        try:
            # Hold the event lock through the write so a fast product response
            # cannot be observed before the input that caused it.
            with self._condition:
                self._write_message(
                    {
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt}],
                        },
                    }
                )
                self._emit(
                    AgentEventType.USER_INPUT,
                    text=prompt,
                    session_id=self._session_id,
                    turn_id=handle.turn_id,
                    data={"turn_id": handle.turn_id},
                )
        except BaseException:
            with self._condition:
                self._active_turn = None
            raise
        return handle

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
        accepted = (
            frozenset((event_types,))
            if isinstance(event_types, AgentEventType)
            else frozenset(event_types)
        )
        if not accepted or not all(
            isinstance(item, AgentEventType) for item in accepted
        ):
            raise ValueError("event_types must be nonempty")
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                for event in self._events:
                    if (
                        event.sequence > after_sequence
                        and event.event_type in accepted
                        and (predicate is None or predicate(event))
                    ):
                        return event
                self._ensure_healthy(allow_clean_exit=True)
                if self._process.poll() is not None:
                    raise RuntimeError(
                        "CodeBuddy process exited before the expected event was observed"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    names = ", ".join(sorted(item.value for item in accepted))
                    raise TimeoutError(f"timed out waiting for CodeBuddy event: {names}")
                self._condition.wait(remaining)

    def wait_for_completion(
        self,
        turn: TurnHandle,
        *,
        timeout: float | None = None,
    ) -> TurnResult:
        terminal = self.wait_for_event(
            AgentEventType.TURN_COMPLETED,
            timeout=self.default_timeout if timeout is None else timeout,
            after_sequence=turn.after_sequence,
            predicate=lambda event: event.turn_id == turn.turn_id,
        )
        data = terminal.data if isinstance(terminal.data, dict) else {}
        subtype = str(data.get("subtype") or "")
        response = data.get("result")
        response_text = response if isinstance(response, str) else terminal.text
        error_items = data.get("errors")
        errors = (
            "\n".join(str(item) for item in error_items)
            if isinstance(error_items, list)
            else ""
        )
        stderr = "\n".join(
            line
            for sequence, line in self._stderr
            if turn.after_sequence < sequence <= terminal.sequence
        )
        if errors:
            stderr = "\n".join(part for part in (stderr, errors) if part)
        raw_output = "\n".join(
            line
            for sequence, line in self._raw_stdout
            if turn.after_sequence < sequence <= terminal.sequence
        )
        duration_ms = data.get("duration_ms")
        duration = (
            float(duration_ms) / 1000.0
            if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool)
            else max(0.0, terminal.monotonic_seconds - turn.sent_at_monotonic)
        )
        completed = (
            subtype == "success"
            and data.get("is_error") is not True
            and bool(response_text.strip())
        )
        return TurnResult(
            response=response_text,
            raw_output=raw_output,
            stderr=stderr,
            returncode=0 if self._process.poll() is None else self._process.returncode,
            completed=completed,
            duration_seconds=duration,
            session_id=terminal.session_id or self._session_id,
        )

    def respond_to_confirmation(
        self,
        event: AgentEvent,
        decision: PermissionDecision,
        *,
        reason: str,
        updated_input: dict[str, JsonValue] | None = None,
    ) -> None:
        if event.event_type is not AgentEventType.PERMISSION_REQUEST:
            raise ValueError("event is not a permission request")
        if not isinstance(decision, PermissionDecision):
            raise ValueError("decision must be a PermissionDecision")
        if not event.request_id:
            raise ValueError("permission request has no request_id")
        if event.session_id not in {None, self._session_id}:
            raise ValueError("permission request belongs to another session")
        request = event.data if isinstance(event.data, dict) else {}
        tool_use_id = request.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            raise ValueError("permission request has no tool_use_id")
        if decision is not PermissionDecision.ALLOW and updated_input is not None:
            raise ValueError("updated_input is only valid for an allow decision")
        if updated_input is not None and not _is_json_value(updated_input):
            raise ValueError("updated_input must contain only JSON values")
        response: dict[str, JsonValue] = {
            "allowed": decision is PermissionDecision.ALLOW,
            "reason": reason,
            "tool_use_id": tool_use_id,
            "interrupt": decision is PermissionDecision.CANCEL,
        }
        if updated_input is not None:
            response["updatedInput"] = updated_input
        with self._condition:
            if event.request_id in self._answered_permission_requests:
                raise ValueError("permission request has already been answered")
            self._write_message(
                {
                    "type": "control_response",
                    "response": {
                        "subtype": "success",
                        "request_id": event.request_id,
                        "response": response,
                    },
                }
            )
            self._emit(
                AgentEventType.PERMISSION_DECISION,
                session_id=self._session_id,
                request_id=event.request_id,
                turn_id=event.turn_id,
                data={
                    "decision": decision.value,
                    "reason": reason,
                    "tool_use_id": tool_use_id,
                    "updated_input": updated_input,
                },
            )
            self._answered_permission_requests.add(event.request_id)

    def steer(
        self,
        text: str,
        *,
        timeout: float | None = None,
        expected_request_id: str | None = None,
    ) -> ControlResult:
        if not text.strip():
            raise ValueError("steer text must be nonempty")
        request: dict[str, JsonValue] = {
            "session_id": self.session_id,
            "content_blocks": [{"type": "text", "text": text}],
        }
        if expected_request_id:
            request["expected_request_id"] = expected_request_id
        return self._send_control(
            "steer",
            request,
            timeout=self.default_timeout if timeout is None else timeout,
        )

    def interrupt_task(
        self,
        *,
        reason: str,
        timeout: float | None = None,
    ) -> ControlResult:
        if not reason.strip():
            raise ValueError("interrupt reason must be nonempty")
        return self._send_control(
            "interrupt",
            {"session_id": self.session_id, "reason": reason},
            timeout=self.default_timeout if timeout is None else timeout,
        )

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        try:
            if self._process.stdin is not None and not self._process.stdin.closed:
                self._process.stdin.close()
            try:
                self._process.wait(timeout=self.close_timeout)
            except subprocess.TimeoutExpired:
                self._terminate_process()
                try:
                    self._process.wait(timeout=self.close_timeout)
                except subprocess.TimeoutExpired:
                    self._kill_process()
                    self._process.wait(timeout=self.close_timeout)
        finally:
            self._wait_thread.join(timeout=self.close_timeout)
            self._stdout_thread.join(timeout=self.close_timeout)
            self._stderr_thread.join(timeout=self.close_timeout)
            try:
                if self._wait_thread.is_alive():
                    raise RuntimeError(
                        "CodeBuddy process exit observer did not stop after cleanup"
                    )
            finally:
                self._call_close_callback()

    def _send_control(
        self,
        subtype: str,
        fields: Mapping[str, JsonValue],
        *,
        timeout: float,
    ) -> ControlResult:
        request_id = f"ats_{subtype}_{uuid.uuid4().hex}"
        with self._condition:
            after_sequence = self._next_sequence - 1
        request: dict[str, JsonValue] = {"subtype": subtype, **fields}
        with self._condition:
            self._write_message(
                {
                    "type": "control_request",
                    "request_id": request_id,
                    "request": request,
                }
            )
            self._emit(
                AgentEventType.CONTROL_REQUEST,
                session_id=self._session_id,
                request_id=request_id,
                turn_id=self._active_turn.turn_id if self._active_turn else None,
                data=cast(JsonValue, _safe_control_request(request)),
            )
        event = self.wait_for_event(
            AgentEventType.CONTROL_RESPONSE,
            timeout=timeout,
            after_sequence=after_sequence,
            predicate=lambda item: item.request_id == request_id,
        )
        data = event.data if isinstance(event.data, dict) else {}
        response = data.get("response")
        normalized = cast(JsonValue, response if isinstance(response, dict) else {})
        success = data.get("subtype") == "success"
        if success and subtype == "steer":
            success = isinstance(response, dict) and response.get("steered") is True
        if success and subtype == "interrupt":
            success = (
                isinstance(response, dict) and response.get("interrupted") is True
            )
        error = str(data.get("error") or "")
        if not success and not error and isinstance(response, dict):
            error = str(response.get("reason") or f"{subtype} was not applied")
        return ControlResult(
            request_id=request_id,
            success=success,
            data=normalized,
            error=error,
        )

    def _write_message(self, payload: Mapping[str, Any]) -> None:
        self._ensure_healthy()
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            stdin = self._process.stdin
            if stdin is None or stdin.closed or self._process.poll() is not None:
                raise RuntimeError("CodeBuddy interactive STDIN is closed")
            try:
                stdin.write(serialized + "\n")
                stdin.flush()
            except (BrokenPipeError, OSError) as error:
                raise RuntimeError("failed to write CodeBuddy interactive STDIN") from error

    def _read_stdout(self) -> None:
        stdout = self._process.stdout
        if stdout is None:
            return
        try:
            for raw_line in stdout:
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                if len(line) > self.max_line_chars:
                    raise RuntimeError("CodeBuddy protocol line exceeds configured limit")
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    self._emit(
                        AgentEventType.PROTOCOL_ERROR,
                        text="invalid CodeBuddy NDJSON message",
                        data={"line_length": len(line)},
                    )
                    raise RuntimeError("invalid CodeBuddy NDJSON message")
                if not isinstance(payload, dict):
                    self._emit(
                        AgentEventType.PROTOCOL_ERROR,
                        text="CodeBuddy NDJSON root is not an object",
                        data={"root_type": type(payload).__name__},
                    )
                    raise RuntimeError("CodeBuddy NDJSON root is not an object")
                self._normalize_stdout(payload, raw_line=line)
        except BaseException as error:
            self._set_collector_error(error)

    def _read_stderr(self) -> None:
        stderr = self._process.stderr
        if stderr is None:
            return
        try:
            for raw_line in stderr:
                line = raw_line.rstrip("\r\n")
                if line:
                    self._emit(AgentEventType.STDERR, text=line, data={"line": line})
        except BaseException as error:
            self._set_collector_error(error)

    def _wait_for_exit(self) -> None:
        returncode = self._process.wait()
        self._stdout_thread.join(timeout=self.close_timeout)
        self._stderr_thread.join(timeout=self.close_timeout)
        try:
            self._emit(
                AgentEventType.SESSION_EXITED,
                session_id=self._session_id,
                data={"returncode": returncode},
            )
        except BaseException as error:
            self._set_collector_error(error)

    def _normalize_stdout(self, payload: dict[str, Any], *, raw_line: str) -> None:
        message_type = payload.get("type")
        session_id = _optional_text(payload.get("session_id")) or self._session_id
        request_id = _request_id(payload)
        active_turn = self._active_turn
        turn_id = active_turn.turn_id if active_turn is not None else None

        if message_type == "assistant":
            message = payload.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type")
                    if part_type == "text" and isinstance(part.get("text"), str):
                        self._emit(
                            AgentEventType.TEXT,
                            text=part["text"],
                            session_id=session_id,
                            request_id=request_id,
                            turn_id=turn_id,
                            data={"content_type": "text"},
                            raw_line=raw_line,
                        )
                    elif part_type == "thinking" and isinstance(
                        part.get("thinking"), str
                    ):
                        self._emit(
                            AgentEventType.THINKING,
                            text=part["thinking"],
                            session_id=session_id,
                            request_id=request_id,
                            turn_id=turn_id,
                            data={"content_type": "thinking"},
                            raw_line=raw_line,
                        )
                    elif part_type == "tool_use":
                        self._emit(
                            AgentEventType.TOOL_CALL,
                            session_id=session_id,
                            request_id=request_id,
                            turn_id=turn_id,
                            data=_select(
                                part,
                                "id",
                                "name",
                                "input",
                            ),
                            raw_line=raw_line,
                        )
            return

        if message_type == "user":
            message = payload.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        self._emit(
                            AgentEventType.TOOL_RESULT,
                            session_id=session_id,
                            request_id=request_id,
                            turn_id=turn_id,
                            data=_select(
                                part,
                                "tool_use_id",
                                "content",
                                "is_error",
                            ),
                            raw_line=raw_line,
                        )
            return

        if message_type == "result":
            result_data = _select(
                payload,
                "subtype",
                "is_error",
                "result",
                "duration_ms",
                "duration_api_ms",
                "num_turns",
                "permission_denials",
                "errors",
                "errors_info",
                "usage",
            )
            self._emit(
                AgentEventType.TURN_COMPLETED,
                text=_optional_text(payload.get("result")) or "",
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                data=result_data,
                raw_line=raw_line,
            )
            with self._condition:
                if self._active_turn is not None and self._active_turn.turn_id == turn_id:
                    self._active_turn = None
            return

        if message_type == "control_request":
            request = payload.get("request")
            subtype = request.get("subtype") if isinstance(request, dict) else None
            event_type = (
                AgentEventType.PERMISSION_REQUEST
                if subtype == "can_use_tool"
                else AgentEventType.CONTROL_REQUEST
            )
            self._emit(
                event_type,
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                data=cast(JsonValue, _safe_control_request(request)),
                raw_line=raw_line,
            )
            return

        if message_type == "control_response":
            response = payload.get("response")
            self._emit(
                AgentEventType.CONTROL_RESPONSE,
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                data=cast(JsonValue, _safe_control_response(response)),
                raw_line=raw_line,
            )
            return

        if message_type == "system":
            subtype = payload.get("subtype")
            event_type = _system_event_type(subtype, payload)
            selected = _system_data(subtype, payload)
            self._emit(
                event_type,
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                data=selected,
                raw_line=raw_line,
            )
            return

        if message_type == "stream_event":
            stream_event = payload.get("event")
            delta = (
                stream_event.get("delta") if isinstance(stream_event, dict) else None
            )
            if isinstance(delta, dict):
                delta_type = delta.get("type")
                if delta_type == "text_delta" and isinstance(delta.get("text"), str):
                    self._emit(
                        AgentEventType.TEXT_DELTA,
                        text=delta["text"],
                        session_id=session_id,
                        request_id=request_id,
                        turn_id=turn_id,
                        data={"content_type": "text_delta"},
                        raw_line=raw_line,
                    )
                    return
                if delta_type == "thinking_delta" and isinstance(
                    delta.get("thinking"), str
                ):
                    self._emit(
                        AgentEventType.THINKING_DELTA,
                        text=delta["thinking"],
                        session_id=session_id,
                        request_id=request_id,
                        turn_id=turn_id,
                        data={"content_type": "thinking_delta"},
                        raw_line=raw_line,
                    )
                    return
            self._emit(
                AgentEventType.RAW,
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                data={"type": "stream_event", "event": cast(JsonValue, payload.get("event"))},
                raw_line=raw_line,
            )
            return

        self._emit(
            AgentEventType.RAW,
            session_id=session_id,
            request_id=request_id,
            turn_id=turn_id,
            data={"type": str(message_type or "unknown")},
            raw_line=raw_line,
        )

    def _emit(
        self,
        event_type: AgentEventType,
        *,
        text: str = "",
        session_id: str | None = None,
        request_id: str | None = None,
        turn_id: str | None = None,
        data: JsonValue | None = None,
        raw_line: str | None = None,
    ) -> AgentEvent:
        with self._condition:
            if len(self._events) >= self.max_events:
                raise RuntimeError("CodeBuddy interactive event limit exceeded")
            sequence = self._next_sequence
            self._next_sequence += 1
            event = AgentEvent(
                sequence=sequence,
                event_type=event_type,
                observed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                monotonic_seconds=time.monotonic(),
                session_id=session_id,
                request_id=request_id,
                turn_id=turn_id,
                text=text,
                data={} if data is None else data,
            )
            self._events.append(event)
            if raw_line is not None:
                self._raw_stdout.append((sequence, raw_line))
            if event_type is AgentEventType.STDERR:
                self._stderr.append((sequence, text))
            try:
                if self._event_sink is not None:
                    self._event_sink(event)
            except BaseException as error:
                self._collector_error = error
                self._condition.notify_all()
                raise
            self._condition.notify_all()
            return event

    def _ensure_healthy(self, *, allow_clean_exit: bool = False) -> None:
        if self._collector_error is not None:
            raise RuntimeError("CodeBuddy interactive event collection failed") from self._collector_error
        if self._closed:
            raise RuntimeError("CodeBuddy interactive session is closed")
        returncode = self._process.poll()
        if returncode is not None and not (allow_clean_exit and returncode == 0):
            raise RuntimeError(f"CodeBuddy interactive process exited with {returncode}")

    def _set_collector_error(self, error: BaseException) -> None:
        with self._condition:
            if self._collector_error is None:
                self._collector_error = error
            self._condition.notify_all()

    def _terminate_process(self) -> None:
        if self._process.poll() is not None:
            return
        if os.name != "nt":
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
                return
            except ProcessLookupError:
                return
        self._process.terminate()

    def _kill_process(self) -> None:
        if self._process.poll() is not None:
            return
        if os.name != "nt":
            try:
                os.killpg(self._process.pid, signal.SIGKILL)
                return
            except ProcessLookupError:
                return
        self._process.kill()

    def _call_close_callback(self) -> None:
        if self._close_callback_called:
            return
        self._close_callback_called = True
        if self._close_callback is not None:
            self._close_callback()


def _request_id(payload: Mapping[str, Any]) -> str | None:
    direct = payload.get("request_id") or payload.get("_requestId")
    if isinstance(direct, str) and direct:
        return direct
    response = payload.get("response")
    if isinstance(response, dict):
        value = response.get("request_id")
        if isinstance(value, str) and value:
            return value
    return None


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _select(payload: Mapping[str, Any], *names: str) -> dict[str, JsonValue]:
    return {
        name: cast(JsonValue, payload[name])
        for name in names
        if name in payload and _is_json_value(payload[name])
    }


def _safe_control_request(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        return {}
    subtype = value.get("subtype")
    if subtype == "can_use_tool":
        return _select(
            value,
            "subtype",
            "tool_name",
            "input",
            "tool_use_id",
            "agent_id",
            "permission_suggestions",
            "blocked_path",
            "decision_reason",
        )
    return _select(value, "subtype", "session_id", "reason")


def _safe_control_response(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        return {}
    result = _select(value, "subtype", "request_id", "error")
    response = value.get("response")
    if isinstance(response, dict):
        result["response"] = _select(
            response,
            "session_id",
            "interrupted",
            "steered",
            "reason",
            "currentModelId",
            "permissionMode",
            "canRewind",
            "filesChanged",
            "insertions",
            "deletions",
            "historyRewound",
            "fileRewindError",
        )
    return result


def _system_event_type(subtype: object, payload: Mapping[str, Any]) -> AgentEventType:
    if subtype == "init":
        return AgentEventType.SESSION_STARTED
    if subtype == "mcp_status":
        return AgentEventType.MCP_STATUS
    if subtype == "task_started":
        return AgentEventType.TASK_STARTED
    if subtype == "task_progress":
        return AgentEventType.TASK_PROGRESS
    if subtype == "task_updated":
        patch = payload.get("patch")
        status = patch.get("status") if isinstance(patch, dict) else None
        return _terminal_task_type(status) or AgentEventType.TASK_UPDATED
    if subtype == "task_notification":
        status = payload.get("status")
        return _terminal_task_type(status) or AgentEventType.TASK_UPDATED
    return AgentEventType.RAW


def _terminal_task_type(status: object) -> AgentEventType | None:
    if status == "completed":
        return AgentEventType.TASK_COMPLETED
    if status == "failed":
        return AgentEventType.TASK_FAILED
    if status in {"stopped", "killed", "cancelled", "canceled"}:
        return AgentEventType.TASK_CANCELLED
    return None


def _system_data(subtype: object, payload: Mapping[str, Any]) -> dict[str, JsonValue]:
    if subtype == "init":
        return _select(
            payload,
            "subtype",
            "cwd",
            "tools",
            "mcp_servers",
            "model",
            "permissionMode",
            "output_style",
        )
    return _select(
        payload,
        "subtype",
        "event",
        "servers",
        "total_count",
        "name",
        "state",
        "error",
        "completed",
        "total",
        "failed",
        "timed_out",
        "task_id",
        "tool_use_id",
        "status",
        "patch",
        "usage",
        "summary",
    )


def _is_json_value(value: object, *, depth: int = 0) -> bool:
    if depth > 32:
        return False
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item, depth=depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item, depth=depth + 1)
            for key, item in value.items()
        )
    return False
