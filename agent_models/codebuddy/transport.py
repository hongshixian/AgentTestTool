"""STDIO transport for CodeBuddy Code CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StdioResponse:
    stdout: str
    stderr: str
    returncode: int
    duration_seconds: float


class CodeBuddyStdioTransport:
    """Execute one CodeBuddy print-mode turn with the prompt on stdin."""

    def __init__(
        self,
        *,
        workspace: Path,
        executable: str = "codebuddy",
        default_timeout: float = 90.0,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.default_timeout = default_timeout

    def is_available(self) -> bool:
        return shutil.which(self.executable) is not None

    def request(
        self,
        prompt: str,
        *,
        timeout: float | None = None,
        session_id: str | None = None,
        resume: bool = False,
        allow_tools: bool = False,
        extra_args: Sequence[str] = (),
    ) -> StdioResponse:
        command = [
            self.executable,
            "--print",
            "--output-format",
            "json",
        ]
        if allow_tools:
            command.append("--dangerously-skip-permissions")
        else:
            command.extend(["--tools", ""])
        if session_id:
            command.extend(["--resume" if resume else "--session-id", session_id])
        else:
            command.append("--no-session-persistence")
        command.extend(extra_args)

        process_environment = os.environ.copy()
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
            timeout=timeout or self.default_timeout,
        )
        return StdioResponse(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            duration_seconds=time.monotonic() - started,
        )

    def close(self) -> None:
        """Print mode owns no long-running process."""
