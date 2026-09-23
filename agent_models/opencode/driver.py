"""Run OpenCode's public headless JSON CLI in an isolated test profile."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from agent_models.interaction import AgentEvent, PermissionPolicy
from agent_models.opencode.profile import OpenCodeTestProfile
from agent_models.processes import run_managed_process
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult


def _permission_rules(
    policy: PermissionPolicy, *, allow_tools: bool, has_mock: bool
) -> dict[str, str]:
    if policy is PermissionPolicy.ASK:
        raise ValueError("one-shot OpenCode calls cannot answer permission requests")
    rules = {"*": "deny"}
    if allow_tools:
        rules.update({"read": "allow", "glob": "allow", "grep": "allow", "list": "allow"})
        if has_mock:
            rules["ats_mock_*"] = "allow"
    if policy is PermissionPolicy.ALLOW_WORKSPACE_EDITS and allow_tools:
        rules["edit"] = "allow"
    return rules


class OpenCodeDriver:
    """Translate one OpenCode JSON event stream into a normalized turn."""

    def __init__(
        self,
        *,
        workspace: Path,
        profile: OpenCodeTestProfile,
        executable: str = "opencode",
        default_timeout: float = 120.0,
    ) -> None:
        self.workspace = workspace
        self.profile = profile
        self.executable = executable
        self.default_timeout = default_timeout

    def check_installation(self) -> InstallationResult:
        resolved = shutil.which(self.executable)
        return InstallationResult(
            installed=resolved is not None,
            detail=("OpenCode CLI is installed" if resolved else "opencode executable not found"),
            executable=resolved,
        )

    def check_authentication(self) -> AuthResult:
        if not self.check_installation().installed:
            return AuthResult(AuthStatus.ERROR, "opencode executable not found")
        result = self.send_prompt("只回复 AUTH_OK。", timeout=60.0, allow_tools=False)
        if result.completed and result.response.strip():
            return AuthResult(AuthStatus.AUTHENTICATED, "OpenCode test model is available")
        return AuthResult(
            AuthStatus.UNAUTHENTICATED,
            (result.stderr.strip() or "OpenCode test model did not complete")[-400:],
        )

    def send_prompt(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
        has_mock: bool = False,
    ) -> TurnResult:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        rules = _permission_rules(permission_policy, allow_tools=allow_tools, has_mock=has_mock)
        command = [
            self.executable, "run", "--format", "json",
            "--model", self.profile.model, "--dir", str(self.workspace),
        ]
        if self.profile.hook_capture is None:
            command.insert(2, "--pure")
        if session_id:
            command.extend(("--session", session_id))
        if permission_policy is PermissionPolicy.BYPASS and allow_tools:
            command.append("--auto")
        command.append(prompt)
        environment = self.profile.process_environment(permission=rules)
        if not allow_tools:
            overlay = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
            saved = json.loads(self.profile.config_file.read_text(encoding="utf-8"))
            configured_tools = saved.get("tools", {})
            # Override explicit enabled patterns as well as tools not listed in the profile.
            overlay["tools"] = {"*": False, **{
                name: False for name in configured_tools if isinstance(name, str)
            }}
            environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(overlay, ensure_ascii=False)
        started = time.monotonic()
        try:
            result = run_managed_process(
                command,
                cwd=self.workspace,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout if timeout is not None else self.default_timeout,
            )
        except subprocess.TimeoutExpired:
            return TurnResult(
                response="", raw_output="", stderr="OpenCode turn timed out",
                returncode=-1, completed=False,
                duration_seconds=time.monotonic() - started, session_id=session_id,
            )
        stdout = result.stdout.replace(self.profile.secret, "[REDACTED]")
        stderr = result.stderr.replace(self.profile.secret, "[REDACTED]")
        return self.parse_output(
            stdout, stderr=stderr, returncode=result.returncode,
            duration_seconds=time.monotonic() - started, fallback_session_id=session_id,
        )

    @staticmethod
    def parse_output(
        output: str,
        *,
        stderr: str = "",
        returncode: int = 0,
        duration_seconds: float = 0.0,
        fallback_session_id: str | None = None,
    ) -> TurnResult:
        events: list[dict[str, Any]] = []
        malformed = False
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed = True
                continue
            if not isinstance(event, dict):
                malformed = True
                continue
            events.append(event)
        session_ids: set[str] = set()
        invalid_session = False
        response: list[str] = []
        terminal = False
        failed = False
        for event in events:
            event_type = event.get("type")
            part = event.get("part")
            outer = event.get("sessionID")
            nested = part.get("sessionID") if isinstance(part, dict) else None
            if (
                ("sessionID" in event and (not isinstance(outer, str) or not outer))
                or (isinstance(part, dict) and "sessionID" in part
                    and (not isinstance(nested, str) or not nested))
                or (outer is not None and nested is not None and outer != nested)
            ):
                invalid_session = True
            sid = outer or nested
            if isinstance(sid, str) and sid:
                session_ids.add(sid)
            else:
                invalid_session = True
            if event_type == "text" and isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    response.append(text)
            elif event_type == "step_finish":
                reason = part.get("reason") if isinstance(part, dict) else None
                if reason == "stop":
                    terminal = True
                elif reason in ("error", "abort"):
                    failed = True
            elif event_type == "error":
                failed = True
                if not stderr:
                    error = event.get("error")
                    if isinstance(error, dict):
                        stderr = str(error.get("name") or "OpenCode model error")[:200]
                    else:
                        stderr = "OpenCode model error"
        if len(session_ids) != 1 or (
            fallback_session_id is not None and session_ids != {fallback_session_id}
        ):
            invalid_session = True
        session_id = fallback_session_id if invalid_session else next(iter(session_ids))
        text = "" if invalid_session else "".join(response)
        if malformed and not stderr:
            stderr = "OpenCode returned malformed JSON events"
        if invalid_session and not stderr:
            stderr = "OpenCode returned missing or inconsistent session identifiers"
        if not terminal and not stderr:
            stderr = "OpenCode did not emit a terminal step"
        completed = (
            bool(text.strip()) and terminal and not failed and not malformed
            and not invalid_session and returncode == 0
        )
        if not completed and not stderr:
            stderr = "OpenCode response was incomplete"
        return TurnResult(
            response=text, raw_output=output, stderr=stderr,
            returncode=returncode, completed=completed,
            duration_seconds=duration_seconds, session_id=session_id,
        )

    def start_session(
        self,
        *,
        timeout: float | None = None,
        permission_policy: PermissionPolicy = PermissionPolicy.ASK,
        mcp_config: Mapping[str, Any] | None = None,
        allow_tools: bool = True,
        event_sink: Callable[[AgentEvent], None] | None = None,
        close_callback: Callable[[], None] | None = None,
    ):
        from agent_models.opencode.interactive import OpenCodeInteractiveSession

        return OpenCodeInteractiveSession(
            workspace=self.workspace,
            environment=self.profile.process_environment(
                permission={"*": "ask"} if permission_policy is PermissionPolicy.ASK else {"*": "deny"}
            ),
            model=self.profile.model,
            timeout=timeout or self.default_timeout,
            permission_policy=permission_policy,
            allow_tools=allow_tools,
            mcp_config=dict(mcp_config or {}),
            executable=self.executable,
            pure=self.profile.hook_capture is None,
            event_sink=event_sink,
            close_callback=close_callback,
        )
