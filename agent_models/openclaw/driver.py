"""Run OpenClaw's embedded agent through its public CLI, one bounded process per turn."""

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

from agent_models.interaction import PermissionPolicy
from agent_models.openclaw.profile import PROVIDER_ID, OpenClawTestProfile
from agent_models.processes import run_managed_process

_VERSION = re.compile(r"OpenClaw\s+(\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Write-capable built-ins; group:fs alone also removes read access, which stays allowed.
_WRITE_TOOLS = ("write", "edit", "apply_patch")
# Gateway, messaging, device and scheduling surfaces are outside the evaluator workspace.
_ALWAYS_DENIED = ("group:automation", "group:messaging", "group:nodes", "group:ui")
# The product's own command timeout stays above the driver bound so the driver owns timeouts.
_PRODUCT_TIMEOUT_MARGIN = 60


def resolve_executable(executable: str) -> Path | None:
    found = shutil.which(executable)
    return Path(found) if found else None


def installed_version(executable: Path, *, timeout: float = 60.0) -> str | None:
    try:
        completed = run_managed_process(
            (str(executable), "--version"), timeout=timeout, capture_output=True, text=True,
            env=_base_environment(executable), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _VERSION.search(_ANSI.sub("", completed.stdout or ""))
    return match.group(1) if match else None


def _base_environment(executable: Path) -> dict[str, str]:
    """Return a minimal environment; secrets of the test harness are never inherited."""
    path = [str(executable.resolve().parent)]
    node = shutil.which("node")
    if node:
        path.append(str(Path(node).resolve().parent))
    path.extend(os.defpath.split(os.pathsep))
    environment = {"PATH": os.pathsep.join(dict.fromkeys(item for item in path if item))}
    for name in ("HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    return environment


def tool_denials(policy: PermissionPolicy, *, allow_tools: bool,
                 hidden_mock_tools: frozenset[str] = frozenset()) -> list[str]:
    """Map the declared permission policy onto OpenClaw's config-layer tool policy."""
    if not allow_tools:
        return ["*"]
    denied: list[str] = [*_ALWAYS_DENIED, *(f"ats_mock__{name}" for name in sorted(hidden_mock_tools))]
    if policy is PermissionPolicy.BYPASS:
        return denied
    denied.append("group:runtime")
    if policy is PermissionPolicy.DENY_UNAPPROVED:
        denied.extend(_WRITE_TOOLS)
    return denied


@dataclass(frozen=True, slots=True)
class McpServer:
    command: str
    args: tuple[str, ...]


@dataclass(slots=True)
class TurnOutcome:
    """Normalized result of one CLI turn."""

    session_id: str
    response: str = ""
    ok: bool = False
    returncode: int | None = None
    timed_out: bool = False
    error: str = ""
    tool_names: tuple[str, ...] = ()
    duration_seconds: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)
    stderr_tail: str = ""


class OpenClawDriver:
    """Own a private config, home and state root; tools act only in the evaluator workspace."""

    def __init__(self, profile: OpenClawTestProfile, *, executable: Path, workspace: Path) -> None:
        self.profile = profile
        self.executable = executable
        self.workspace = workspace.resolve()
        self._root = Path(tempfile.mkdtemp(prefix="ats-openclaw-"))
        self.home = self._root / "home"
        self.state = self.home / "state"
        self.state.mkdir(parents=True)
        self.config_path = self._root / "openclaw.json"
        self.mcp: McpServer | None = None

    def _config(self, policy: PermissionPolicy, allow_tools: bool, hidden: frozenset[str]) -> dict[str, Any]:
        provider = {
            "baseUrl": self.profile.base_url,
            # Inline key: a ${VAR} reference would leak through the exec tool's inherited environment.
            "apiKey": self.profile.api_key,
            "api": "openai-completions",
            "models": [{"id": self.profile.model, "name": self.profile.model, "reasoning": False,
                        "input": ["text"], "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                        "contextWindow": 128000, "maxTokens": 8192}],
        }
        config: dict[str, Any] = {
            "update": {"checkOnStart": False},
            "models": {"providers": {PROVIDER_ID: provider}},
            "agents": {"defaults": {"model": {"primary": self.profile.model_ref},
                                    "workspace": str(self.workspace), "skipBootstrap": True}},
            "tools": {"profile": "coding", "fs": {"workspaceOnly": True},
                      "deny": tool_denials(policy, allow_tools=allow_tools, hidden_mock_tools=hidden)},
        }
        if self.mcp is not None:
            config["mcp"] = {"servers": {"ats_mock": {"command": self.mcp.command, "args": list(self.mcp.args)}}}
        return config

    def _write_config(self, config: dict[str, Any]) -> None:
        descriptor = os.open(self.config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(config, handle)

    def run_turn(self, prompt: str, *, session_id: str, timeout: float, policy: PermissionPolicy,
                 allow_tools: bool, hidden_mock_tools: frozenset[str] = frozenset()) -> TurnOutcome:
        self._write_config(self._config(policy, allow_tools, hidden_mock_tools))
        message = self._root / "prompt.txt"
        message.write_text(prompt, encoding="utf-8")
        environment = _base_environment(self.executable)
        environment.update(OPENCLAW_HOME=str(self.home), OPENCLAW_STATE_DIR=str(self.state),
                           OPENCLAW_CONFIG_PATH=str(self.config_path))
        command = (str(self.executable), "agent", "--local", "--session-id", session_id,
                   "--message-file", str(message), "--json",
                   "--timeout", str(int(timeout) + _PRODUCT_TIMEOUT_MARGIN))
        started = time.monotonic()
        outcome = TurnOutcome(session_id=session_id)
        try:
            completed = run_managed_process(command, timeout=timeout, capture_output=True, text=True,
                                            encoding="utf-8", errors="replace", env=environment,
                                            cwd=self.workspace, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            outcome.timed_out = True
            outcome.error = f"OpenClaw turn exceeded {timeout:.0f}s; process tree stopped"
            outcome.duration_seconds = time.monotonic() - started
            return outcome
        finally:
            message.unlink(missing_ok=True)
        outcome.duration_seconds = time.monotonic() - started
        outcome.returncode = completed.returncode
        outcome.stderr_tail = _ANSI.sub("", completed.stderr or "")[-2000:]
        parse_envelope(completed.stdout or "", outcome)
        return outcome

    def close(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)


def parse_envelope(stdout: str, outcome: TurnOutcome) -> None:
    """Fill ``outcome`` from the CLI JSON envelope; anything else is a protocol error."""
    try:
        data = json.loads(stdout)
    except ValueError:
        outcome.error = "OpenClaw did not print a JSON result" + (f": {stdout[-300:]}" if stdout.strip() else "")
        return
    if not isinstance(data, dict):
        outcome.error = "OpenClaw JSON result is not an object"
        return
    error = data.get("error")
    if data.get("ok") is False or error:
        outcome.error = (error.get("message") if isinstance(error, dict) else str(error or "")) or "OpenClaw turn failed"
        return
    payloads = data.get("payloads") if isinstance(data.get("payloads"), list) else []
    texts = [item["text"] for item in payloads if isinstance(item, dict) and isinstance(item.get("text"), str)]
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    receipt = agent_meta.get("terminalReceipt") if isinstance(agent_meta.get("terminalReceipt"), dict) else {}
    outcome.response = "\n\n".join(texts)
    outcome.tool_names = tuple(name for name in receipt.get("successfulToolNames") or () if isinstance(name, str))
    outcome.meta = {key: meta.get(key) for key in ("durationMs", "aborted", "stopReason")}
    outcome.meta.update({key: agent_meta.get(key) for key in ("sessionId", "provider", "model", "assistantTurns")})
    if meta.get("aborted"):
        outcome.error = "OpenClaw reported the turn as aborted"
        return
    outcome.ok = outcome.returncode in (0, None)
