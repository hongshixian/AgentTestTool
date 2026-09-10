"""Unified test driver for CodeBuddy Code CLI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

from agent_models.codebuddy.interactive import CodeBuddyInteractiveSession
from agent_models.interaction import (
    AgentEvent,
    BackgroundTaskControlResult,
    BackgroundTaskHandle,
    BackgroundTaskObservation,
    PermissionPolicy,
)
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from configs.environment import agent_process_environment


class CodeBuddyDriver:
    """Drive CodeBuddy process, authentication, sessions and output normalization."""

    AUTHENTICATION_PROBE = "这是自动化认证状态检查。请只回复 AUTH_OK。"

    def __init__(
        self,
        *,
        workspace: Path,
        executable: str = "codebuddy",
        default_timeout: float = 90.0,
        config_dir: Path | None = None,
    ) -> None:
        configured_dir = os.environ.get("CODEBUDDY_CONFIG_DIR")
        self.workspace = workspace
        self.executable = executable
        self.default_timeout = default_timeout
        self.is_dedicated_test_account = config_dir is not None or bool(configured_dir)
        self.config_dir = config_dir or (
            Path(configured_dir).expanduser()
            if configured_dir
            else Path.home() / ".codebuddy"
        )
        self._interactive_sessions: list[CodeBuddyInteractiveSession] = []
        self._interactive_lock = threading.RLock()
        self._background_task_ids: set[str] = set()
        self._background_lock = threading.RLock()

    def is_available(self) -> bool:
        """Return whether the CodeBuddy executable can be resolved."""

        return shutil.which(self.executable) is not None

    def check_installation(self) -> InstallationResult:
        """Resolve the configured CodeBuddy executable without starting a session."""

        executable = shutil.which(self.executable)
        if executable is None:
            return InstallationResult(False, "找不到 codebuddy 命令")
        return InstallationResult(
            True,
            "CodeBuddy CLI 命令已安装",
            executable=executable,
        )

    def check_authentication(self) -> AuthResult:
        """Actively verify the selected CodeBuddy profile can use the model service."""

        if not self.is_available():
            return AuthResult(AuthStatus.ERROR, "找不到 codebuddy 命令")
        if not self._has_local_login_state():
            return AuthResult(AuthStatus.UNAUTHENTICATED, "未发现 CodeBuddy 本地登录状态")

        try:
            turn = self.send_prompt(self.AUTHENTICATION_PROBE, timeout=60.0)
        except subprocess.TimeoutExpired:
            return AuthResult(AuthStatus.ERROR, "CodeBuddy 认证探测超时")

        if turn.completed:
            return AuthResult(AuthStatus.AUTHENTICATED, "CodeBuddy 认证探测成功")
        detail = turn.stderr.strip() or turn.response.strip() or "CodeBuddy 认证探测失败"
        return AuthResult(AuthStatus.UNAUTHENTICATED, detail[-500:])

    def login(self) -> AuthResult:
        """Direct users to CodeBuddy's own interactive login flow."""

        return AuthResult(
            status=AuthStatus.UNAUTHENTICATED,
            detail="请先运行 codebuddy 并使用产品登录流程完成认证",
        )

    def send_prompt(
        self,
        prompt: str,
        *,
        timeout: float | None = None,
        session_id: str | None = None,
        resume: bool = False,
        allow_tools: bool = False,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
        extra_args: Sequence[str] = (),
    ) -> TurnResult:
        """Execute one CodeBuddy turn over STDIO and normalize its output."""

        command = [self.executable, "--print", "--output-format", "json"]
        if not allow_tools:
            command.extend(["--tools", ""])
        permission_modes = {
            PermissionPolicy.ASK: "default",
            PermissionPolicy.DENY_UNAPPROVED: "dontAsk",
            PermissionPolicy.ALLOW_WORKSPACE_EDITS: "acceptEdits",
            PermissionPolicy.BYPASS: "bypassPermissions",
        }
        try:
            permission_mode = permission_modes[permission_policy]
        except KeyError as error:
            raise ValueError("unsupported permission policy") from error
        command.extend(("--permission-mode", permission_mode))
        if session_id:
            command.extend(["--resume" if resume else "--session-id", session_id])
        else:
            command.append("--no-session-persistence")
        command.extend(extra_args)

        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)
        if allow_tools:
            process_environment["CODEBUDDY_IS_SANDBOX"] = "1"

        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt + "\n",
            cwd=self.workspace,
            env=process_environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.default_timeout if timeout is None else timeout,
        )
        return self.parse_output(
            completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            duration_seconds=time.monotonic() - started,
        )

    def start_session(
        self,
        *,
        session_id: str,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.ASK,
        extra_args: Sequence[str] = (),
        event_sink: Callable[[AgentEvent], None] | None = None,
        close_callback: Callable[[], None] | None = None,
    ) -> CodeBuddyInteractiveSession:
        """Start the public persistent STDIO stream-json protocol."""

        command = [
            self.executable,
            "--print",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--session-id",
            session_id,
            "--no-session-persistence",
        ]
        if not allow_tools:
            command.extend(("--tools", ""))
        permission_modes = {
            PermissionPolicy.ASK: "default",
            PermissionPolicy.DENY_UNAPPROVED: "dontAsk",
            PermissionPolicy.ALLOW_WORKSPACE_EDITS: "acceptEdits",
            PermissionPolicy.BYPASS: "bypassPermissions",
        }
        try:
            permission_mode = permission_modes[permission_policy]
        except KeyError as error:
            raise ValueError("unsupported permission policy") from error
        command.extend(("--permission-mode", permission_mode))
        command.extend(extra_args)

        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)

        session: CodeBuddyInteractiveSession | None = None

        def closed() -> None:
            if session is not None:
                with self._interactive_lock:
                    if session in self._interactive_sessions:
                        self._interactive_sessions.remove(session)
            if close_callback is not None:
                close_callback()

        session = CodeBuddyInteractiveSession(
            command=command,
            workspace=self.workspace,
            environment=process_environment,
            session_id=session_id,
            default_timeout=self.default_timeout if timeout is None else timeout,
            event_sink=event_sink,
            close_callback=closed,
        )
        with self._interactive_lock:
            self._interactive_sessions.append(session)
        return session

    def start_background_task(
        self,
        prompt: str,
        *,
        name: str,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
        extra_args: Sequence[str] = (),
    ) -> BackgroundTaskHandle:
        """Start a product-managed task through the public ``--bg`` entry."""

        if not prompt.strip():
            raise ValueError("background task prompt must be nonempty")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name) is None:
            raise ValueError("background task name must be a safe identifier")
        permission_modes = {
            PermissionPolicy.ASK: "default",
            PermissionPolicy.DENY_UNAPPROVED: "dontAsk",
            PermissionPolicy.ALLOW_WORKSPACE_EDITS: "acceptEdits",
            PermissionPolicy.BYPASS: "bypassPermissions",
        }
        try:
            permission_mode = permission_modes[permission_policy]
        except KeyError as error:
            raise ValueError("unsupported permission policy") from error
        command = [
            self.executable,
            "--bg",
            "--name",
            name,
            "--permission-mode",
            permission_mode,
        ]
        if not allow_tools:
            command.extend(("--tools", ""))
        command.extend(extra_args)
        command.append(prompt)
        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)
        if allow_tools:
            process_environment["CODEBUDDY_IS_SANDBOX"] = "1"
        completed = subprocess.run(
            command,
            cwd=self.workspace,
            env=process_environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.default_timeout if timeout is None else timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"CodeBuddy background task launch failed (exit {completed.returncode})"
            )
        match = re.search(
            r"backgrounded\s*[·•]\s*([A-Za-z0-9][A-Za-z0-9_-]{0,127})",
            completed.stdout,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise RuntimeError("CodeBuddy background task launch returned no task ID")
        task_id = match.group(1)
        with self._background_lock:
            self._background_task_ids.add(task_id)
        observations = {
            item.task_id: item for item in self.observe_background_tasks()
        }
        observation = observations.get(task_id)
        return BackgroundTaskHandle(
            task_id=task_id,
            name=name,
            session_id=observation.session_id if observation is not None else None,
        )

    def observe_background_tasks(
        self,
        *,
        timeout: float | None = None,
    ) -> tuple[BackgroundTaskObservation, ...]:
        """Read the public JSON background-task inventory."""

        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)
        completed = subprocess.run(
            [self.executable, "agents", "--jobs", "--all"],
            cwd=self.workspace,
            env=process_environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.default_timeout if timeout is None else timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"CodeBuddy background inventory failed (exit {completed.returncode})"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("CodeBuddy background inventory returned invalid JSON") from error
        if not isinstance(payload, list):
            raise RuntimeError("CodeBuddy background inventory must be a JSON array")
        observations: list[BackgroundTaskObservation] = []
        for item in payload:
            if not isinstance(item, dict):
                raise RuntimeError("CodeBuddy background inventory item must be an object")
            task_id = item.get("id")
            name = item.get("name")
            kind = item.get("kind")
            state = item.get("state")
            session_id = item.get("sessionId")
            if not all(
                isinstance(value, str) and value
                for value in (task_id, name, kind, state)
            ):
                raise RuntimeError("CodeBuddy background inventory item is incomplete")
            if session_id is not None and not isinstance(session_id, str):
                raise RuntimeError("CodeBuddy background session ID must be text")
            started_at = item.get("startedAt")
            if type(started_at) not in (str, int, float, type(None)):
                raise RuntimeError("CodeBuddy background start time is invalid")
            observations.append(
                BackgroundTaskObservation(
                    task_id=task_id,
                    name=name,
                    kind=kind,
                    state=state,
                    session_id=session_id,
                    started_at=started_at,
                )
            )
        return tuple(observations)

    def read_background_task_logs(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> str:
        """Read the public log stream retained for one background task."""

        self._validate_background_task_id(task_id)
        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)
        completed = subprocess.run(
            [self.executable, "logs", task_id],
            cwd=self.workspace,
            env=process_environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.default_timeout if timeout is None else timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"CodeBuddy background log query failed (exit {completed.returncode})"
            )
        if len(completed.stdout) > 1_048_576:
            raise RuntimeError("CodeBuddy background log exceeds evidence limit")
        return completed.stdout

    def stop_background_task(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> BackgroundTaskControlResult:
        """Request termination through the public ``stop`` command."""

        self._validate_background_task_id(task_id)
        process_environment = agent_process_environment()
        process_environment["CODEBUDDY_CONFIG_DIR"] = str(self.config_dir)
        completed = subprocess.run(
            [self.executable, "stop", task_id],
            cwd=self.workspace,
            env=process_environment,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.default_timeout if timeout is None else timeout,
        )
        result = BackgroundTaskControlResult(
            task_id=task_id,
            success=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return result

    @staticmethod
    def _validate_background_task_id(task_id: str) -> None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", task_id) is None:
            raise ValueError("invalid background task ID")

    @property
    def interactive_sessions(self) -> tuple[CodeBuddyInteractiveSession, ...]:
        """Return sessions retained for runtime evidence until Model cleanup."""

        with self._interactive_lock:
            return tuple(self._interactive_sessions)

    @staticmethod
    def parse_output(
        stdout: str,
        *,
        stderr: str = "",
        returncode: int = 0,
        duration_seconds: float = 0.0,
    ) -> TurnResult:
        """Normalize one CodeBuddy JSON output stream into a public turn result."""

        items = _parse_output_items(stdout)
        result_item = next(
            (
                item
                for item in reversed(items)
                if isinstance(item, dict) and item.get("type") == "result"
            ),
            None,
        )

        if result_item is None:
            assistant_item, assistant_text = _last_assistant_text(items)
            return TurnResult(
                response=assistant_text,
                raw_output=stdout,
                stderr=stderr,
                returncode=returncode,
                completed=False,
                duration_seconds=duration_seconds,
                session_id=_session_id(assistant_item),
            )

        text = result_item.get("result")
        turn_completed = (
            returncode == 0
            and result_item.get("subtype") == "success"
            and result_item.get("is_error") is not True
            and isinstance(text, str)
            and bool(text.strip())
        )
        return TurnResult(
            response=text if isinstance(text, str) else "",
            raw_output=stdout,
            stderr=stderr,
            returncode=returncode,
            completed=turn_completed,
            duration_seconds=duration_seconds,
            session_id=result_item.get("session_id"),
        )

    def close(self, *, session_id: str | None = None) -> None:
        """Release driver-owned resources and remove the test session record."""

        with self._interactive_lock:
            sessions = tuple(self._interactive_sessions)
        errors: list[BaseException] = []
        for session in sessions:
            try:
                session.close()
            except BaseException as error:
                errors.append(error)

        with self._background_lock:
            background_task_ids = tuple(self._background_task_ids)
        if background_task_ids:
            terminal_states = {
                "done",
                "failed",
                "cancelled",
                "canceled",
                "stopped",
                "killed",
            }
            try:
                observations = {
                    item.task_id: item for item in self.observe_background_tasks()
                }
            except BaseException:
                observations = {}
            for task_id in background_task_ids:
                observed = observations.get(task_id)
                if (
                    observed is not None
                    and observed.state.casefold() in terminal_states
                ):
                    with self._background_lock:
                        self._background_task_ids.discard(task_id)
                    continue
                try:
                    result = self.stop_background_task(task_id)
                    if not result.success:
                        raise RuntimeError(
                            "CodeBuddy background task cleanup failed "
                            f"(exit {result.returncode})"
                        )
                except BaseException as error:
                    errors.append(error)

        if session_id is not None:
            projects = self.config_dir / "projects"
            if projects.is_dir():
                session_name = f"{session_id}.jsonl"
                for root, directories, files in os.walk(
                    projects,
                    topdown=True,
                    followlinks=False,
                    onerror=lambda _error: None,
                ):
                    root_path = Path(root)
                    directories[:] = [
                        name
                        for name in directories
                        if not (root_path / name).is_symlink()
                    ]
                    if session_name not in files:
                        continue
                    session_file = root_path / session_name
                    session_file.unlink(missing_ok=True)
                    try:
                        root_path.rmdir()
                    except OSError:
                        pass
        if errors:
            raise BaseExceptionGroup("CodeBuddy interactive session cleanup failed", errors)

    def _has_local_login_state(self) -> bool:
        storage = self.config_dir / "local_storage"
        return storage.is_dir() and any(storage.iterdir())


def _parse_output_items(raw_output: str) -> list[Any]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return _parse_complete_array_items(raw_output)
    return payload if isinstance(payload, list) else [payload]


def _parse_complete_array_items(raw_output: str) -> list[Any]:
    stripped = raw_output.lstrip()
    if not stripped.startswith("["):
        return []

    decoder = json.JSONDecoder()
    index = raw_output.index("[") + 1
    items: list[Any] = []
    while index < len(raw_output):
        while index < len(raw_output) and raw_output[index] in " \t\r\n,":
            index += 1
        if index >= len(raw_output) or raw_output[index] == "]":
            break
        try:
            item, index = decoder.raw_decode(raw_output, index)
        except json.JSONDecodeError:
            break
        items.append(item)
    return items


def _last_assistant_text(items: list[Any]) -> tuple[dict[str, Any] | None, str]:
    for item in reversed(items):
        if not isinstance(item, dict) or item.get("type") != "assistant":
            continue
        message = item.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        texts = [
            part.get("text")
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        ]
        if texts:
            return item, "\n".join(texts)
    return None, ""


def _session_id(item: dict[str, Any] | None) -> str | None:
    if item is None:
        return None
    value = item.get("session_id") or item.get("sessionId")
    return value if isinstance(value, str) else None
