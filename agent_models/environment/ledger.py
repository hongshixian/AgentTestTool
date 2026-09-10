"""Persist bounded, redacted observation evidence with an integrity chain."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_models.evidence import JsonValue


class EvidenceLedgerError(RuntimeError):
    """Evidence collection is incomplete or no longer writable."""


_REDACTED = "[REDACTED]"
_ZERO_HASH = "0" * 64
_SENSITIVE = re.compile(
    r"password|passwd|secret|token|authorization|credential|cookie|api[_-]?key|private[_-]?key",
    re.IGNORECASE,
)
_ASSIGNMENT = re.compile(
    r"(?i)((?:password|passwd|secret|[\w-]*token|api[_-]?key|credential)"
    r"\s*[=:]\s*)([^\s&,;]+)"
)
_HEADER = re.compile(r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+")
_BEARER = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_URL_AUTH = re.compile(r"(?i)(https?://)[^\s/@]+@")


def _encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class EvidenceLedger:
    """A run-local evidence store, not isolation from another process of the same user.

    Hash chains detect accidental or partial changes; they are not signatures or
    protection against an actor who can rewrite the entire store and its manifest.
    Healthy empty collection never proves that an unobserved action did not occur.
    """

    def __init__(
        self,
        directory: Path,
        run_id: str | None = None,
        secrets: Sequence[str] = (),
        *,
        workspace: Path | None = None,
        max_events: int = 100_000,
        max_event_bytes: int = 1_048_576,
        max_total_bytes: int = 67_108_864,
    ) -> None:
        self.directory = Path(directory).resolve()
        if workspace is not None:
            root = Path(workspace).resolve()
            if self.directory == root or self.directory.is_relative_to(root) or root.is_relative_to(self.directory):
                raise ValueError("Evidence and workspace directories must be disjoint")
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (max_events, max_event_bytes, max_total_bytes)):
            raise ValueError("Evidence capacities must be positive integers")
        self.run_id = uuid4().hex if run_id is None else run_id
        if not isinstance(self.run_id, str) or not self.run_id or len(self.run_id) > 256:
            raise ValueError("run_id must contain 1 to 256 characters")
        if any(not isinstance(secret, str) for secret in secrets):
            raise ValueError("secrets must contain strings")
        self._secrets = tuple(sorted({s for s in secrets if s}, key=len, reverse=True))
        self._secret_prefixes: tuple[str, ...] = ()
        if self._text(self.run_id) != self.run_id:
            raise ValueError("run_id must not contain credentials")
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._errors: list[str] = []
        self._closed = False
        self._manifest_hash: str | None = None
        self._bytes = 0
        self._max_events, self._max_event_bytes, self._max_total_bytes = max_events, max_event_bytes, max_total_bytes
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if any(self.directory.iterdir()):
            raise ValueError("Evidence directory must be empty; existing evidence is never overwritten")
        self._path = self.directory / "events.jsonl"
        self._write_new(self._path, b"")

    def _text(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, _REDACTED)
        for prefix in self._secret_prefixes:
            value = re.sub(
                re.escape(prefix) + r"[A-Za-z0-9_.:/+=-]*",
                _REDACTED,
                value,
            )
        value = _URL_AUTH.sub(r"\1[REDACTED]@", value)
        value = _HEADER.sub(r"\1[REDACTED]", value)
        value = _BEARER.sub(r"\1 [REDACTED]", value)
        return _ASSIGNMENT.sub(r"\1[REDACTED]", value)

    def register_secrets(
        self,
        secrets: Sequence[str] = (),
        *,
        prefixes: Sequence[str] = (),
    ) -> None:
        """Redact dynamically created values from all subsequent evidence.

        Prefixes cover streaming protocol fragments where a generated value can
        be split before the complete secret is available to the ledger.
        """

        if isinstance(secrets, str) or isinstance(prefixes, str):
            raise ValueError("secrets and prefixes must be sequences of strings")
        if any(not isinstance(value, str) for value in (*secrets, *prefixes)):
            raise ValueError("secrets and prefixes must contain strings")
        with self._lock:
            self._writable()
            self._secrets = tuple(
                sorted(
                    {*self._secrets, *(value for value in secrets if value)},
                    key=len,
                    reverse=True,
                )
            )
            self._secret_prefixes = tuple(
                sorted(
                    {*self._secret_prefixes, *(value for value in prefixes if value)},
                    key=len,
                    reverse=True,
                )
            )

    def redact(self, value: Any, *, _depth: int = 0) -> JsonValue:
        """Return a detached JSON value, redacting nested and JSON-encoded credentials."""
        if _depth > 32:
            raise ValueError("Evidence nesting exceeds 32 levels")
        if isinstance(value, str):
            if value.lstrip().startswith(("{", "[")):
                try:
                    parsed = json.loads(value)
                except (ValueError, RecursionError):
                    pass
                else:
                    # Leaf values are already redacted. Applying line-oriented
                    # header patterns to serialized JSON would consume its syntax.
                    return _encode(self.redact(parsed, _depth=_depth + 1)).decode()
            return self._text(value)
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Evidence must contain finite JSON numbers")
            return value
        if isinstance(value, (list, tuple)):
            return [self.redact(item, _depth=_depth + 1) for item in value]
        if isinstance(value, dict):
            if not all(isinstance(key, str) for key in value):
                raise ValueError("Evidence object keys must be strings")
            return {
                self._text(key): _REDACTED if _SENSITIVE.search(key) else self.redact(item, _depth=_depth + 1)
                for key, item in value.items()
            }
        raise ValueError("Evidence must be JSON serializable")

    def _fail(self, reason: str) -> None:
        if reason not in self._errors:
            self._errors.append(reason)
        raise EvidenceLedgerError(reason)

    def _writable(self) -> None:
        if self._closed:
            raise EvidenceLedgerError("Evidence ledger is closed")
        if self._errors:
            raise EvidenceLedgerError("Evidence collector is unhealthy")

    def _write_new(self, path: Path, content: bytes) -> None:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self._fail("Evidence file creation failed")

    def _append(self, content: bytes) -> None:
        if self._path.is_symlink():
            self._fail("Evidence file became a symbolic link")
        try:
            flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self._path, flags)
            with os.fdopen(descriptor, "ab") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self._fail("Evidence append failed")

    def record(self, source: str, kind: str, data: JsonValue, correlation_id: str | None = None) -> dict[str, Any]:
        """Append one observation; capacity, serialization and I/O errors fail closed."""
        with self._lock:
            self._writable()
            if not isinstance(source, str) or not source or not isinstance(kind, str) or not kind:
                self._fail("Evidence source and kind must be nonempty strings")
            if correlation_id is not None and not isinstance(correlation_id, str):
                self._fail("Evidence correlation_id must be a string")
            try:
                event = {
                    "sequence": len(self._events) + 1,
                    "run_id": self.run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "monotonic_ns": time.monotonic_ns(),
                    "source": self._text(source),
                    "kind": self._text(kind),
                    "correlation_id": self._text(correlation_id) if correlation_id is not None else None,
                    "data": self.redact(data),
                    "previous_hash": self._events[-1]["hash"] if self._events else _ZERO_HASH,
                }
                event["hash"] = hashlib.sha256(_encode(event)).hexdigest()
                encoded = _encode(event) + b"\n"
            except (ValueError, TypeError, RecursionError):
                self._fail("Evidence serialization failed")
            if len(self._events) >= self._max_events or len(encoded) > self._max_event_bytes or self._bytes + len(encoded) > self._max_total_bytes:
                self._fail("Evidence capacity exceeded")
            self._append(encoded)
            self._bytes += len(encoded)
            self._events.append(event)
            return copy.deepcopy(event)

    @property
    def events(self) -> list[dict[str, Any]]:
        return self.snapshot()

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._events)

    def save_artifact(self, name: str, payload: Any) -> Path:
        """Save a bounded JSON artifact and link its content hash into the event chain."""
        with self._lock:
            self._writable()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}(?:\.json)?", name):
                raise ValueError("Artifact name must be a simple JSON filename")
            filename = name if name.endswith(".json") else name + ".json"
            if filename in {"manifest.json", "events.jsonl"} or filename in self._artifacts:
                raise ValueError("Artifact already exists or uses a reserved name")
            try:
                content = _encode(self.redact(payload)) + b"\n"
            except (ValueError, TypeError, RecursionError):
                self._fail("Artifact serialization failed")
            if len(content) > self._max_event_bytes or self._bytes + len(content) > self._max_total_bytes:
                self._fail("Evidence capacity exceeded")
            path = self.directory / filename
            self._write_new(path, content)
            self._bytes += len(content)
            info = {"filename": filename, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            self._artifacts[filename] = info
            self.record("ledger", "artifact_saved", info)
            return path

    def archive_bundle(self, bundle: Any, name: str = "evidence_bundle") -> Path:
        """Archive an EvidenceBundle or compatible JSON payload without changing its claims."""
        if is_dataclass(bundle) and not isinstance(bundle, type):
            # Judge payloads may truncate raw output; persistence must not do so.
            payload = asdict(bundle)
        elif callable(getattr(bundle, "judge_payload", None)):
            payload = bundle.judge_payload()
        elif callable(getattr(bundle, "to_dict", None)):
            payload = bundle.to_dict()
        else:
            payload = bundle
        if isinstance(payload, dict) and payload.get("run_id", self.run_id) != self.run_id:
            raise ValueError("EvidenceBundle belongs to a different run")
        return self.save_artifact(name, payload)

    @staticmethod
    def verify_archive(directory: Path, run_id: str | None = None, *, max_bytes: int = 67_108_864) -> dict[str, Any]:
        """Check a closed archive after the collector exits, without modifying it.

        This verifies internal consistency, not authenticity of a manifest that an
        attacker could replace together with every evidence file.
        """
        errors: list[str] = []
        count = 0
        observed_run = run_id
        total_bytes = 0

        def read_file(filename: str) -> bytes:
            nonlocal total_bytes
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,110}", filename):
                raise ValueError("Invalid archived filename")
            path = Path(directory) / filename
            size = path.stat().st_size
            total_bytes += size
            if path.is_symlink() or total_bytes > max_bytes:
                raise ValueError("Invalid archived file")
            return path.read_bytes()

        try:
            manifest = json.loads(read_file("manifest.json"))
            observed_run = manifest["run_id"]
            if run_id is not None and observed_run != run_id:
                errors.append("Manifest run mismatch")
            if manifest.get("schema_version") != 1 or not manifest["healthy"] or manifest["errors"]:
                errors.append("Manifest reports incomplete evidence")
            raw = read_file("events.jsonl")
            if raw and not raw.endswith(b"\n"):
                errors.append("Event stream is truncated")
            previous = _ZERO_HASH
            artifact_events: dict[str, Any] = {}
            for count, line in enumerate(raw.splitlines(), start=1):
                event = json.loads(line)
                digest = event.pop("hash")
                if event["run_id"] != observed_run or event["sequence"] != count:
                    errors.append("Event run or sequence mismatch")
                if event["previous_hash"] != previous or hashlib.sha256(_encode(event)).hexdigest() != digest:
                    errors.append("Event hash chain mismatch")
                if event["source"] == "ledger" and event["kind"] == "artifact_saved":
                    info = event["data"]
                    if info["filename"] in artifact_events:
                        errors.append("Duplicate artifact event")
                    artifact_events[info["filename"]] = info
                previous = digest
            if count != manifest["event_count"] or previous != manifest["last_hash"]:
                errors.append("Manifest event anchor mismatch")
            artifacts = {info["filename"]: info for info in manifest["artifacts"]}
            if len(artifacts) != len(manifest["artifacts"]) or artifacts != artifact_events:
                errors.append("Manifest artifact anchor mismatch")
            for filename, info in artifacts.items():
                content = read_file(filename)
                if len(content) != info["bytes"] or hashlib.sha256(content).hexdigest() != info["sha256"]:
                    errors.append("Artifact integrity mismatch")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            errors.append("Archive is missing, malformed or exceeds capacity")
        return {"healthy": not errors, "errors": list(dict.fromkeys(errors)), "event_count": count, "run_id": observed_run}

    def verify(self) -> dict[str, Any]:
        """Compare persisted evidence against sequence, hashes and this process's anchors."""
        with self._lock:
            errors: list[str] = []
            try:
                if self._path.is_symlink() or self._path.stat().st_size > self._max_total_bytes:
                    raise ValueError("invalid file")
                raw = self._path.read_bytes()
                lines = raw.splitlines()
                if raw and not raw.endswith(b"\n"):
                    errors.append("Event stream is truncated")
                if len(lines) != len(self._events):
                    errors.append("Event count differs from collector anchor")
                previous = _ZERO_HASH
                for index, line in enumerate(lines):
                    event = json.loads(line)
                    digest = event.pop("hash")
                    if event["run_id"] != self.run_id or event["sequence"] != index + 1:
                        errors.append("Event run or sequence mismatch")
                    if event["previous_hash"] != previous or hashlib.sha256(_encode(event)).hexdigest() != digest:
                        errors.append("Event hash chain mismatch")
                    if index >= len(self._events) or digest != self._events[index]["hash"]:
                        errors.append("Event differs from collector anchor")
                    previous = digest
                for filename, info in self._artifacts.items():
                    artifact = self.directory / filename
                    if artifact.is_symlink() or artifact.stat().st_size != info["bytes"] or hashlib.sha256(artifact.read_bytes()).hexdigest() != info["sha256"]:
                        errors.append("Artifact integrity mismatch")
                if self._closed:
                    manifest = self.directory / "manifest.json"
                    if manifest.is_symlink() or manifest.stat().st_size > self._max_total_bytes or hashlib.sha256(manifest.read_bytes()).hexdigest() != self._manifest_hash:
                        errors.append("Manifest integrity mismatch")
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                errors.append("Evidence is missing or malformed")
            for error in errors:
                if error not in self._errors:
                    self._errors.append(error)
            return {"healthy": not self._errors, "errors": list(self._errors), "event_count": len(self._events), "run_id": self.run_id}

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {**self.verify(), "closed": self._closed, "bytes": self._bytes, "has_observations": any(e["source"] != "ledger" for e in self._events)}

    def close(self) -> dict[str, Any]:
        """Persist completion or failure metadata; never remove captured evidence."""
        with self._lock:
            if self._closed:
                return self.health()
            self.verify()
            manifest = {
                "schema_version": 1, "run_id": self.run_id,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "event_count": len(self._events),
                "last_hash": self._events[-1]["hash"] if self._events else _ZERO_HASH,
                "healthy": not self._errors, "errors": list(self._errors),
                "artifacts": list(self._artifacts.values()),
                "integrity_scope": "Hash chain, not authenticated storage or proof of unobserved absence",
            }
            content = _encode(manifest) + b"\n"
            self._write_new(self.directory / "manifest.json", content)
            self._manifest_hash = hashlib.sha256(content).hexdigest()
            self._closed = True
            return self.health()

    def __enter__(self) -> EvidenceLedger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
