"""Run Codex through its public ``codex exec`` CLI, one bounded process per turn."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_models.codex.profile import CodexTestProfile
from agent_models.interaction import PermissionPolicy
from agent_models.processes import run_managed_process

_VERSION = re.compile(r"codex-cli\s+(\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)")
MOCK_SERVER = "ats_mock"
# Variables Codex needs to start; harness secrets (Judge keys etc.) are never inherited.
_PASSTHROUGH = ("HOME", "LANG", "LC_ALL", "TMPDIR", "CODEX_HOME",
                "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "no_proxy", "all_proxy",
                "SYSTEMROOT", "USERPROFILE", "APPDATA", "LOCALAPPDATA")


def resolve_executable(executable: str) -> Path | None:
    found = shutil.which(executable)
    return Path(found) if found else None


def child_environment(executable: Path) -> dict[str, str]:
    """Whitelist environment; the user's ``CODEX_HOME`` still provides authentication."""
    path = [str(executable.resolve().parent)]
    node = shutil.which("node")
    if node:
        path.append(str(Path(node).resolve().parent))
    path.extend(os.defpath.split(os.pathsep))
    environment = {"PATH": os.pathsep.join(dict.fromkeys(item for item in path if item))}
    environment.update({name: os.environ[name] for name in _PASSTHROUGH if os.environ.get(name)})
    return environment


def installed_version(executable: Path, *, timeout: float = 60.0) -> str | None:
    try:
        completed = run_managed_process((str(executable), "--version"), timeout=timeout, capture_output=True,
                                        text=True, env=child_environment(executable), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _VERSION.search(completed.stdout or "")
    return match.group(1) if match else None


def _toml(value: Any) -> str:
    # JSON strings, booleans and string arrays are valid TOML values for `-c key=value`.
    return json.dumps(value, ensure_ascii=False)


def permission_args(policy: PermissionPolicy, *, allow_tools: bool) -> list[str]:
    """Map the declared policy onto Codex sandbox flags; headless runs never prompt."""
    if allow_tools and policy is PermissionPolicy.BYPASS:
        return ["--dangerously-bypass-approvals-and-sandbox"]
    sandbox = ("workspace-write" if allow_tools and policy is PermissionPolicy.ALLOW_WORKSPACE_EDITS
               else "read-only")
    return ["-c", f"sandbox_mode={_toml(sandbox)}", "-c", 'approval_policy="never"']


@dataclass(frozen=True, slots=True)
class McpServer:
    command: str
    args: tuple[str, ...]
    enabled_tools: tuple[str, ...]


@dataclass(slots=True)
class TurnOutcome:
    """Normalized result of one CLI turn."""

    session_id: str | None = None
    response: str = ""
    ok: bool = False
    returncode: int | None = None
    timed_out: bool = False
    error: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    stderr_tail: str = ""


class CodexDriver:
    """Run turns in the evaluator workspace; only the last-message file lives in a private root."""

    def __init__(self, profile: CodexTestProfile, *, executable: Path, workspace: Path) -> None:
        self.profile = profile
        self.executable = executable
        self.workspace = workspace.resolve()
        self._root = Path(tempfile.mkdtemp(prefix="ats-codex-"))
        self.mcp: McpServer | None = None

    def command(self, prompt: str, *, session_id: str | None, policy: PermissionPolicy, allow_tools: bool,
                ephemeral: bool, last_message: Path) -> list[str]:
        options = [
            "-m", self.profile.model,
            "-c", f"model_reasoning_effort={_toml(self.profile.reasoning_effort)}",
            "-c", 'shell_environment_policy.inherit="core"',
            *permission_args(policy, allow_tools=allow_tools),
            "--skip-git-repo-check", "--json", "-o", str(last_message),
        ]
        if ephemeral:
            options.append("--ephemeral")
        if self.mcp is not None and allow_tools:
            prefix = f"mcp_servers.{MOCK_SERVER}"
            options += ["-c", f"{prefix}.command={_toml(self.mcp.command)}",
                        "-c", f"{prefix}.args={_toml(list(self.mcp.args))}",
                        "-c", f"{prefix}.enabled_tools={_toml(list(self.mcp.enabled_tools))}",
                        "-c", f'{prefix}.default_tools_approval_mode="approve"']
        base = [str(self.executable), "exec", "--color", "never"]
        if session_id is None:
            return [*base, "--cd", str(self.workspace), *options, "--", prompt]
        # `resume` rejects --cd/--sandbox; the stored thread keeps its working root.
        return [*base, "resume", *options, "--", session_id, prompt]

    def run_turn(self, prompt: str, *, session_id: str | None, timeout: float, policy: PermissionPolicy,
                 allow_tools: bool, ephemeral: bool = False) -> TurnOutcome:
        last_message = self._root / "last-message.txt"
        last_message.unlink(missing_ok=True)
        command = self.command(prompt, session_id=session_id, policy=policy, allow_tools=allow_tools,
                               ephemeral=ephemeral, last_message=last_message)
        started = time.monotonic()
        outcome = TurnOutcome(session_id=session_id)
        try:
            completed = run_managed_process(command, timeout=timeout, capture_output=True, text=True,
                                            encoding="utf-8", errors="replace", cwd=self.workspace,
                                            env=child_environment(self.executable), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            outcome.timed_out = True
            outcome.error = f"Codex turn exceeded {timeout:.0f}s; process tree stopped"
            outcome.duration_seconds = time.monotonic() - started
            return outcome
        outcome.duration_seconds = time.monotonic() - started
        outcome.returncode = completed.returncode
        outcome.stderr_tail = (completed.stderr or "")[-2000:]
        parse_events(completed.stdout or "", outcome)
        if last_message.exists():
            outcome.response = last_message.read_text(encoding="utf-8", errors="replace").strip() or outcome.response
        outcome.ok = outcome.ok and completed.returncode == 0
        if not outcome.ok and not outcome.error:
            outcome.error = f"codex exec exited with {completed.returncode}"
        return outcome

    def close(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)


def parse_events(stdout: str, outcome: TurnOutcome) -> None:
    """Read the JSONL event stream; item-level ``error`` entries are config warnings, not failures."""
    messages: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "thread.started" and isinstance(event.get("thread_id"), str):
            outcome.session_id = event["thread_id"]
        elif kind == "turn.completed":
            outcome.ok = True
            outcome.usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        elif kind in ("turn.failed", "error"):
            outcome.ok = False
            detail = event.get("error") if isinstance(event.get("error"), dict) else event
            outcome.error = str(detail.get("message") or kind)
        elif kind == "item.completed" and isinstance(event.get("item"), dict):
            item = event["item"]
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                messages.append(item["text"])
            elif item.get("type") == "command_execution":
                outcome.tool_calls.append({"type": "command_execution", "command": item.get("command"),
                                           "exit_code": item.get("exit_code"), "status": item.get("status")})
            elif item.get("type") == "mcp_tool_call":
                outcome.tool_calls.append({"type": "mcp_tool_call", "server": item.get("server"),
                                           "tool": item.get("tool"), "status": item.get("status")})
            elif item.get("type") == "file_change":
                outcome.tool_calls.append({"type": "file_change", "status": item.get("status")})
    if messages:
        outcome.response = messages[-1]
