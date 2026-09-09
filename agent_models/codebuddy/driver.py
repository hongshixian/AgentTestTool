"""Unified test driver for CodeBuddy Code CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
        extra_args: Sequence[str] = (),
    ) -> TurnResult:
        """Execute one CodeBuddy turn over STDIO and normalize its output."""

        command = [self.executable, "--print", "--output-format", "json"]
        if allow_tools:
            command.append("--dangerously-skip-permissions")
        else:
            command.extend(["--tools", ""])
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

        if session_id is None:
            return
        projects = self.config_dir / "projects"
        if not projects.is_dir():
            return
        for session_file in projects.rglob(f"{session_id}.jsonl"):
            session_file.unlink(missing_ok=True)
            try:
                session_file.parent.rmdir()
            except OSError:
                pass

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
