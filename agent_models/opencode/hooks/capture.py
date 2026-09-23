"""Own a private OpenCode native-hook log for grey-box observations only."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    EvidenceStatus,
    JsonValue,
)


MAX_HOOK_BYTES = 1024 * 1024
MAX_HOOK_EVENTS = 4096
_ALLOWED_KINDS = frozenset({"chat.params", "tool.execute.before", "tool.execute.after"})
_FIELDS = frozenset({
    "schema_version", "run_id", "session_id", "turn_id", "kind", "observed_at",
    "user_message_id", "model_id", "temperature_set", "top_p_set", "tool_name",
    "tool_call_id",
})
_LIMITATIONS = (
    "chat.params observes option mutations, not the complete provider request or system prompt.",
    "tool.execute hooks do not by themselves prove remote service state or absence of unobserved calls.",
    "Uncorrelated tool hooks cannot be assigned to a user turn without an explicit turn ID.",
)


class OpenCodeHookCapture:
    """Create isolated append-only evidence and expose a grey-box-only plugin.

    The plugin emits *metadata only*: no prompt, arguments, tool output, provider
    options or API keys. The caller must use a per-case private directory apart
    from the workspace and pass the returned environment to the child process.
    An explicit turn_id in that environment is safe only for a single-turn
    subprocess, never a long-lived concurrent server.
    """

    def __init__(self, *, evidence_directory: Path, workspace: Path, run_id: str) -> None:
        if not run_id or len(run_id) > 128 or not all(
            char.isalnum() or char in "_.:-" for char in run_id
        ):
            raise ValueError("hook run_id must be a short, safe identifier")
        root = evidence_directory.resolve()
        work = workspace.resolve()
        if root == work or root.is_relative_to(work):
            raise ValueError("OpenCode native-hook evidence must be outside the workspace")
        if evidence_directory.is_symlink() or not evidence_directory.is_dir():
            raise ValueError("hook evidence directory must exist and not be a symlink")
        if os.name != "nt" and root.stat().st_mode & 0o077:
            raise ValueError("hook evidence directory must be private to the test process")
        self.run_id = run_id
        self.directory = root
        self.path = root / "opencode-native-hooks.jsonl"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        os.close(descriptor)

    def install(self, *, isolated_config_dir: Path) -> Path:
        """Copy into an isolated OpenCode profile's plugin directory."""

        if isolated_config_dir.is_symlink() or not isolated_config_dir.is_dir():
            raise ValueError("isolated OpenCode config directory is unavailable")
        plugin_dir = isolated_config_dir / "plugin"
        plugin_dir.mkdir(mode=0o700, exist_ok=True)
        if plugin_dir.is_symlink():
            raise ValueError("isolated OpenCode plugin directory is a symlink")
        target = plugin_dir / "ats_grey_box.js"
        if target.exists() or target.is_symlink():
            raise ValueError("OpenCode test plugin target already exists")
        shutil.copyfile(Path(__file__).with_name("ats_grey_box.js"), target)
        target.chmod(0o600)
        return target

    def process_environment(
        self, base: Mapping[str, str], *, case_level: str, turn_id: str | None = None
    ) -> dict[str, str]:
        """Inject the capture window exclusively for grey-box test invocations."""

        result = {key: value for key, value in base.items() if not key.startswith("ATS_OC_HOOK_")}
        if case_level != "grey_box":
            return result
        if turn_id is not None and (
            not turn_id or len(turn_id) > 128
            or not all(char.isalnum() or char in "_.:-" for char in turn_id)
        ):
            raise ValueError("hook turn_id must be a short, safe identifier")
        result.update({
            "ATS_OC_HOOK_CASE_LEVEL": "grey_box",
            "ATS_OC_HOOK_FILE": str(self.path),
            "ATS_OC_HOOK_RUN_ID": self.run_id,
        })
        if turn_id is not None:
            result["ATS_OC_HOOK_TURN_ID"] = turn_id
        return result

    def checkpoint(self) -> int:
        """Use the returned offset to isolate a later capture to this turn."""

        return self.path.stat().st_size

    def capture(
        self,
        request: EvidenceRequest,
        *,
        offset: int = 0,
        turn_id: str | None = None,
        redactor: Callable[[Any], JsonValue] | None = None,
        product_version: str | None = None,
    ) -> EvidenceRecord:
        """Capture one bounded window, rejecting malformed or ambiguous evidence."""

        if request.phase is not EvidencePhase.AFTER:
            raise ValueError("native hook evidence is available only after execution")
        if request.context is not None and request.context.run_id != self.run_id:
            raise ValueError("hook evidence run does not match the request")
        source = EvidenceSource(
            provider="opencode_native_plugin", channel="isolated_plugin_hook",
            authority=EvidenceAuthority.PRODUCT_RUNTIME, product="opencode",
            product_version=product_version,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
                raise ValueError("invalid hook evidence offset")
            if self.path.is_symlink():
                raise ValueError("hook evidence file was replaced by a symlink")
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                size = os.fstat(descriptor).st_size
                if size > MAX_HOOK_BYTES or offset > size:
                    raise ValueError("hook evidence file exceeds collection bounds")
                os.lseek(descriptor, offset, os.SEEK_SET)
                content = os.read(descriptor, MAX_HOOK_BYTES + 1)
            finally:
                os.close(descriptor)
            if len(content) > MAX_HOOK_BYTES or (content and not content.endswith(b"\n")):
                raise ValueError("hook evidence contains an incomplete entry")
            raw_events = [json.loads(line) for line in content.splitlines()]
            if len(raw_events) > MAX_HOOK_EVENTS:
                raise ValueError("hook event count exceeds limit")
            if any(not isinstance(event, dict) or event.get("schema_version") != 1
                   or event.get("run_id") != self.run_id
                   or event.get("kind") not in _ALLOWED_KINDS | {"collector_overflow"}
                   or any(key not in _FIELDS for key in event)
                   for event in raw_events):
                raise ValueError("hook event fails schema or run validation")
            if any(event.get("kind") == "collector_overflow" for event in raw_events):
                raise ValueError("hook collector overflowed")
            # A foreign session inside the requested observation window makes
            # event absence and turn correlation ambiguous, so fail closed.
            if request.session_id is not None and any(
                event.get("session_id") != request.session_id for event in raw_events
            ):
                raise ValueError("hook evidence contains another session")
            session_ids = {event.get("session_id") for event in raw_events}
            if raw_events and (len(session_ids) != 1 or None in session_ids):
                raise ValueError("hook events lack a unique session")
            selected_turn_id = turn_id or (
                next(iter({event.get("turn_id") for event in raw_events}))
                if len({event.get("turn_id") for event in raw_events}) == 1 and raw_events
                else None
            )
            if turn_id is not None and any(
                event.get("turn_id") != turn_id for event in raw_events
            ):
                raise ValueError("hook evidence contains another turn")
            if selected_turn_id is None and any(
                event.get("kind", "").startswith("tool.execute") for event in raw_events
            ):
                raise ValueError("tool hook events cannot be attributed to a unique turn")
            if any(not isinstance(event.get("observed_at"), str)
                   or not event["observed_at"] for event in raw_events):
                raise ValueError("hook event timestamp missing")
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as error:
            # Never include untrusted content or file names in diagnostics.
            return EvidenceRecord(
                "opencode_native_hooks", "collection_diagnostic", request.phase,
                {"events": []}, status=EvidenceStatus.UNVERIFIED, source=source,
                correlation=EvidenceCorrelation(run_id=self.run_id),
                limitations=(*_LIMITATIONS, f"Hook window rejected: {type(error).__name__}"),
            )

        events: JsonValue = raw_events
        if redactor is not None:
            events = redactor(raw_events)
        session = next(iter(session_ids)) if raw_events else None
        correlation = EvidenceCorrelation(
            run_id=self.run_id,
            session_ids=(session,) if isinstance(session, str) else (),
            turn_ids=(selected_turn_id,) if selected_turn_id is not None else (),
            tool_use_ids=tuple(sorted({event["tool_call_id"] for event in raw_events
                                        if isinstance(event.get("tool_call_id"), str)})),
        )
        return EvidenceRecord(
            "opencode_native_hooks", "runtime_evidence", request.phase,
            {"events": events, "complete_observation": False},
            status=EvidenceStatus.AVAILABLE if raw_events else EvidenceStatus.MISSING,
            source=source, correlation=correlation,
            proves=("OpenCode executed these instrumented plugin hooks in the selected window",)
            if raw_events else (),
            limitations=_LIMITATIONS,
        )
