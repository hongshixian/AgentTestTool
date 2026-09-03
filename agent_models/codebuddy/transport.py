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
        extra_args: Sequence[str] = (),
    ) -> StdioResponse:
        command = [
            self.executable,
            "--print",
            "--output-format",
            "json",
            "--tools",
            "",
            "--no-session-persistence",
            *extra_args,
        ]
        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt + "\n",
            cwd=self.workspace,
            env=os.environ.copy(),
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

