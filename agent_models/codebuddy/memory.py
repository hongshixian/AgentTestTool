"""Observe and restore CodeBuddy memory files in a dedicated test profile."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceSource,
    JsonValue,
)
from agent_models.memory import MemoryMarker, MemoryStateRequest


@dataclass(frozen=True, slots=True)
class _MemoryArtifact:
    path: Path
    scope: str
    display_path: str
    content: bytes
    mode: int


class CodeBuddyMemoryStateController:
    """Manage only documented local memory artifacts in a disposable profile."""

    MAX_FILES = 1_000
    MAX_FILE_BYTES = 1_000_000
    MAX_TOTAL_BYTES = 20_000_000

    def __init__(
        self,
        *,
        workspace: Path,
        config_dir: Path,
        dedicated_test_account: bool,
    ) -> None:
        self.workspace = workspace.resolve()
        self.config_dir = config_dir.expanduser().resolve()
        self.dedicated_test_account = dedicated_test_account
        self._baselines: dict[str, dict[str, _MemoryArtifact]] = {}

    def is_available(self) -> bool:
        """Require an explicit disposable profile before observing user memory."""

        return self.dedicated_test_account and self.config_dir.is_dir()

    def prepare(self, request: MemoryStateRequest) -> tuple[EvidenceRecord, ...]:
        """Keep an in-memory baseline and return a content-free BEFORE record."""

        self._require_available()
        if request.run_id in self._baselines:
            raise RuntimeError(f"记忆状态运行 {request.run_id} 已存在基线")
        snapshot = self._snapshot()
        self._baselines[request.run_id] = snapshot
        return (self._record(request, EvidencePhase.BEFORE, snapshot),)

    def capture(self, request: MemoryStateRequest) -> tuple[EvidenceRecord, ...]:
        """Return marker hits and file-level differences from the saved baseline."""

        self._require_available()
        baseline = self._baseline(request.run_id)
        current = self._snapshot()
        return (
            self._record(
                request,
                EvidencePhase.AFTER,
                current,
                baseline=baseline,
            ),
        )

    def restore(self, request: MemoryStateRequest) -> tuple[EvidenceRecord, ...]:
        """Restore every observed memory file and remove files created by the run."""

        self._require_available()
        baseline = self._baseline(request.run_id)
        current = self._snapshot()
        baseline_paths = set(baseline)
        for logical_path, artifact in current.items():
            if logical_path not in baseline_paths:
                artifact.path.unlink(missing_ok=True)
        for artifact in baseline.values():
            self._atomic_restore(artifact)
        self._remove_empty_memory_directories()
        restored = self._snapshot()
        if self._fingerprints(restored) != self._fingerprints(baseline):
            raise RuntimeError("CodeBuddy 记忆状态恢复后与基线不一致")
        del self._baselines[request.run_id]
        return (
            EvidenceRecord(
                evidence_id="product_memory_restoration",
                evidence_type="local_state_evidence",
                phase=EvidencePhase.AFTER,
                data={"restored": True, "artifact_count": len(restored)},
                source=self._source(),
                correlation=EvidenceCorrelation(run_id=request.run_id),
                proves=("评测方观察范围内的 CodeBuddy 本地记忆文件已恢复到执行前基线",),
                limitations=("恢复结果不证明云端、缓存或未公开存储载体已经同步恢复。",),
            ),
        )

    def close(self) -> None:
        """Best-effort restore is intentionally strict so leaked state cannot be hidden."""

        errors: list[BaseException] = []
        for run_id in tuple(self._baselines):
            try:
                self.restore(MemoryStateRequest(run_id=run_id))
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("CodeBuddy memory restoration failed", errors)

    def _require_available(self) -> None:
        if not self.is_available():
            raise RuntimeError(
                "CodeBuddy 记忆状态控制仅允许使用已存在的专用 CODEBUDDY_CONFIG_DIR"
            )

    def _baseline(self, run_id: str) -> dict[str, _MemoryArtifact]:
        try:
            return self._baselines[run_id]
        except KeyError as error:
            raise RuntimeError(f"记忆状态运行 {run_id} 缺少执行前基线") from error

    def _candidates(self) -> tuple[tuple[str, str, Path], ...]:
        return (
            ("user", "user/CODEBUDDY.md", self.config_dir / "CODEBUDDY.md"),
            ("user", "user/CODEBUDDY.mdc", self.config_dir / "CODEBUDDY.mdc"),
            ("project", "project/CODEBUDDY.md", self.workspace / "CODEBUDDY.md"),
            ("project", "project/CODEBUDDY.mdc", self.workspace / "CODEBUDDY.mdc"),
            ("project", "project/AGENTS.md", self.workspace / "AGENTS.md"),
            ("project", "project/AGENTS.mdc", self.workspace / "AGENTS.mdc"),
            (
                "project_local",
                "project/CODEBUDDY.local.md",
                self.workspace / "CODEBUDDY.local.md",
            ),
            (
                "project_local",
                "project/CODEBUDDY.local.mdc",
                self.workspace / "CODEBUDDY.local.mdc",
            ),
            (
                "project",
                "project/.codebuddy/CODEBUDDY.md",
                self.workspace / ".codebuddy" / "CODEBUDDY.md",
            ),
            (
                "project",
                "project/.codebuddy/CODEBUDDY.mdc",
                self.workspace / ".codebuddy" / "CODEBUDDY.mdc",
            ),
            (
                "project",
                "project/.codebuddy/AGENTS.md",
                self.workspace / ".codebuddy" / "AGENTS.md",
            ),
            (
                "project",
                "project/.codebuddy/AGENTS.mdc",
                self.workspace / ".codebuddy" / "AGENTS.mdc",
            ),
            (
                "project_local",
                "project/.codebuddy/CODEBUDDY.local.md",
                self.workspace / ".codebuddy" / "CODEBUDDY.local.md",
            ),
            (
                "project_local",
                "project/.codebuddy/CODEBUDDY.local.mdc",
                self.workspace / ".codebuddy" / "CODEBUDDY.local.mdc",
            ),
        )

    def _snapshot(self) -> dict[str, _MemoryArtifact]:
        artifacts: dict[str, _MemoryArtifact] = {}
        for scope, display_path, path in self._candidates():
            if path.exists() or path.is_symlink():
                artifacts[display_path] = self._read_artifact(path, scope, display_path)

        recursive_roots = (
            ("user_rule", "user/rules", self.config_dir / "rules"),
            ("project_rule", "project/.codebuddy/rules", self.workspace / ".codebuddy" / "rules"),
            ("auto_memory", "auto_memory/legacy", self.config_dir / "memories"),
            ("auto_memory", "auto_memory/projects", self.config_dir / "projects"),
        )
        for scope, display_root, root in recursive_roots:
            if root.is_symlink():
                raise RuntimeError(f"CodeBuddy 记忆根目录不得是符号链接：{root}")
            if root.is_dir():
                for path in sorted(root.rglob("*")):
                    if scope == "auto_memory" and display_root.endswith("projects"):
                        relative_parts = path.relative_to(root).parts
                        if not any(part in {"memory", "memories"} for part in relative_parts):
                            continue
                    if path.is_symlink():
                        raise RuntimeError(f"CodeBuddy 记忆文件不得是符号链接：{path}")
                    if not path.is_file():
                        continue
                    relative = path.relative_to(root).as_posix()
                    display_path = f"{display_root}/{relative}"
                    artifacts[display_path] = self._read_artifact(
                        path,
                        scope,
                        display_path,
                    )
                    if len(artifacts) > self.MAX_FILES:
                        raise RuntimeError("CodeBuddy 记忆文件数量超过安全观察上限")

        total_bytes = sum(len(artifact.content) for artifact in artifacts.values())
        if total_bytes > self.MAX_TOTAL_BYTES:
            raise RuntimeError("CodeBuddy 记忆文件总大小超过安全观察上限")
        return artifacts

    def _read_artifact(self, path: Path, scope: str, display_path: str) -> _MemoryArtifact:
        if path.is_symlink():
            raise RuntimeError(f"CodeBuddy 记忆文件不得是符号链接：{path}")
        stat = path.stat()
        if not path.is_file():
            raise RuntimeError(f"CodeBuddy 记忆路径不是普通文件：{display_path}")
        if stat.st_size > self.MAX_FILE_BYTES:
            raise RuntimeError(f"CodeBuddy 记忆文件超过单文件安全上限：{display_path}")
        return _MemoryArtifact(
            path=path,
            scope=scope,
            display_path=display_path,
            content=path.read_bytes(),
            mode=stat.st_mode,
        )

    def _record(
        self,
        request: MemoryStateRequest,
        phase: EvidencePhase,
        snapshot: dict[str, _MemoryArtifact],
        *,
        baseline: dict[str, _MemoryArtifact] | None = None,
    ) -> EvidenceRecord:
        artifacts: list[JsonValue] = []
        marker_locations: dict[str, list[str]] = {
            marker.marker_id: [] for marker in request.markers
        }
        for logical_path, artifact in sorted(snapshot.items()):
            text = artifact.content.decode("utf-8", errors="replace")
            frontmatter_keys = self._frontmatter_keys(text)
            hits = [
                marker.marker_id
                for marker in request.markers
                if marker.value in text
            ]
            for marker_id in hits:
                marker_locations[marker_id].append(logical_path)
            artifacts.append(
                {
                    "scope": artifact.scope,
                    "path": logical_path,
                    "size": len(artifact.content),
                    "sha256": hashlib.sha256(artifact.content).hexdigest(),
                    "marker_hits": hits,
                    "frontmatter_keys": frontmatter_keys,
                }
            )

        data: dict[str, JsonValue] = {
            "artifact_count": len(snapshot),
            "artifacts": artifacts,
            "marker_locations": marker_locations,
        }
        if baseline is not None:
            before = self._fingerprints(baseline)
            after = self._fingerprints(snapshot)
            data["created"] = sorted(after.keys() - before.keys())
            data["deleted"] = sorted(before.keys() - after.keys())
            data["modified"] = sorted(
                path
                for path in before.keys() & after.keys()
                if before[path] != after[path]
            )
        return EvidenceRecord(
            evidence_id="product_memory_state",
            evidence_type="local_state_evidence",
            phase=phase,
            data=data,
            source=self._source(),
            correlation=EvidenceCorrelation(run_id=request.run_id),
            proves=(
                "评测方从 CodeBuddy 公开文档所述本地记忆文件中观察到文件摘要、变化和测试标记命中",
            ),
            limitations=(
                "本地文件观察不能证明记忆已被模型加载、来自哪个原始主体或已从云端和缓存物理删除。",
            ),
        )

    @staticmethod
    def _fingerprints(snapshot: dict[str, _MemoryArtifact]) -> dict[str, str]:
        return {
            path: hashlib.sha256(artifact.content).hexdigest()
            for path, artifact in snapshot.items()
        }

    @staticmethod
    def _frontmatter_keys(text: str) -> list[str]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return []
        keys: list[str] = []
        for line in lines[1:]:
            if line.strip() == "---":
                return sorted(set(keys))
            key, separator, _value = line.partition(":")
            if separator and key.strip():
                keys.append(key.strip().lower())
        return []

    @staticmethod
    def _atomic_restore(artifact: _MemoryArtifact) -> None:
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{artifact.path.name}.",
            dir=artifact.path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(artifact.content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_path, stat.S_IMODE(artifact.mode))
            os.replace(temporary_path, artifact.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _remove_empty_memory_directories(self) -> None:
        root = self.config_dir / "memories"
        if not root.is_dir() or root.is_symlink():
            return
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _source() -> EvidenceSource:
        return EvidenceSource(
            provider="codebuddy_memory_state_controller",
            channel="documented_local_memory_files",
            authority=EvidenceAuthority.EVALUATOR_OBSERVED,
            product="codebuddy",
            observed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        )
