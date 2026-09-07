"""Manage bounded test workspaces without claiming operating-system isolation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import stat
import tempfile
from typing import Iterator


class WorkspaceError(RuntimeError):
    """A workspace operation could not be completed safely."""


@dataclass(frozen=True)
class WorkspaceEntry:
    """An immutable relative directory or regular-file image."""

    path: str
    is_directory: bool
    mode: int
    content: bytes = field(default=b"", repr=False)
    sha256: str = ""


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """An in-memory snapshot bound to its original directory identity."""

    root: Path
    root_identity: tuple[int, int]
    root_mode: int
    entries: tuple[WorkspaceEntry, ...]


@dataclass(frozen=True)
class WorkspaceDiff:
    """Relative paths added, modified, or deleted since a snapshot."""

    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]


def _relative(value: str | Path) -> Path:
    # Native Path objects carry their platform's separator semantics; untyped
    # strings must still use the portable slash-only representation.
    raw = value.as_posix() if isinstance(value, PurePath) else str(value)
    windows = PureWindowsPath(raw)
    # Backslashes and drive paths are rejected even on POSIX to keep semantics portable.
    if not raw or raw == "." or "\\" in raw or windows.drive or windows.root:
        raise WorkspaceError("Expected a nonempty portable relative path")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise WorkspaceError("Workspace path escapes its declared root")
    if any(part.endswith((".", " ")) or PureWindowsPath(part).is_reserved() for part in path.parts):
        raise WorkspaceError("Workspace path uses a nonportable filename")
    return Path(*path.parts)


def _fingerprint(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def _inspect(path: Path) -> os.stat_result:
    info = path.lstat()
    junction = getattr(path, "is_junction", None)
    reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or reparse or (junction is not None and junction()):
        raise WorkspaceError("Workspace links and junctions are not supported")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise WorkspaceError("Workspace special files are not supported")
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise WorkspaceError("Workspace hard-linked files are not supported")
    return info


class WorkspaceManager:
    """Prepare and restore a disposable workspace after stopping its writers.

    This is not an OS sandbox or a race-proof boundary against hostile processes.
    Scans detect observed concurrent changes and fail closed. Snapshots stay in
    memory and may contain raw test data; never serialize them as evidence without
    redaction. Windows restores the permission bits supported by its filesystem.
    """

    def __init__(self, root: Path, assets_root: Path | None = None, *,
                 max_files: int = 10_000, max_bytes: int = 64 * 1024 * 1024) -> None:
        if max_files < 1 or max_bytes < 1:
            raise ValueError("Workspace limits must be positive")
        supplied = Path(root).absolute()
        if supplied.is_symlink():
            raise WorkspaceError("Workspace root must not be a symbolic link")
        self.root = supplied.resolve()
        self.max_files = max_files
        self.max_bytes = max_bytes
        self._guard_root()
        if (self.root / ".git").exists() or (self.root / ".git").is_symlink():
            raise WorkspaceError("Refusing an existing repository root")
        self.root.mkdir(parents=True, exist_ok=True)
        info = _inspect(self.root)
        if not stat.S_ISDIR(info.st_mode):
            raise WorkspaceError("Workspace root must be a directory")
        self._identity = (info.st_dev, info.st_ino)
        self.assets_root: Path | None = None
        if assets_root is not None:
            source = Path(assets_root).absolute()
            if source.is_symlink():
                raise WorkspaceError("Assets root must not be a symbolic link")
            source = source.resolve(strict=True)
            if not stat.S_ISDIR(_inspect(source).st_mode):
                raise WorkspaceError("Assets root must be a directory")
            if source == self.root or source.is_relative_to(self.root) or self.root.is_relative_to(source):
                raise WorkspaceError("Assets and workspace roots must not overlap")
            self.assets_root = source
            source_info = _inspect(source)
            self._assets_identity = (source_info.st_dev, source_info.st_ino)

    def _guard_root(self) -> None:
        protected = {Path.cwd().resolve(), Path.home().resolve()}
        protected.update(Path.cwd().resolve().parents)
        protected.update(Path.home().resolve().parents)
        protected.add(Path(tempfile.gettempdir()).resolve())
        if self.root in protected or len(self.root.parts) < 3:
            raise WorkspaceError("Refusing a home, repository, or broad workspace root")

    def _check_root(self) -> None:
        self._guard_root()
        info = _inspect(self.root)
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self._identity:
            raise WorkspaceError("Workspace root was replaced")

    def _target(self, relative: str | Path, *, base: Path | None = None) -> Path:
        anchor = self.root if base is None else base
        path = anchor
        for part in _relative(relative).parts:
            path = path / part
            if path.exists() or path.is_symlink():
                _inspect(path)
        return path

    def write_bytes(self, relative: str | Path, content: bytes) -> Path:
        """Atomically preseed a regular file inside the declared workspace."""
        if not isinstance(content, bytes):
            raise TypeError("Workspace content must be bytes")
        if len(content) > self.max_bytes:
            raise WorkspaceError("Workspace file exceeds the byte limit")
        self._check_root()
        target = self._target(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._target(relative)
        descriptor, temporary = tempfile.mkstemp(prefix=".workspace-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            self._check_root()
            self._target(relative)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return target

    def write_text(self, relative: str | Path, content: str, *, encoding: str = "utf-8") -> Path:
        """Preseed a text file using an explicit encoding."""
        return self.write_bytes(relative, content.encode(encoding))

    def _inventory(self, root: Path) -> dict[str, tuple[int, ...]]:
        found: dict[str, tuple[int, ...]] = {}
        total = 0
        pending = [root]
        while pending:
            current = pending.pop()
            info = _inspect(current)
            relative = current.relative_to(root).as_posix()
            found[relative] = _fingerprint(info)
            if len(found) > self.max_files + 1:
                raise WorkspaceError("Workspace entry count exceeds the limit")
            if stat.S_ISDIR(info.st_mode):
                pending.extend(sorted(current.iterdir(), reverse=True))
            else:
                total += info.st_size
                if total > self.max_bytes:
                    raise WorkspaceError("Workspace contents exceed the byte limit")
        return found

    def _read_file(self, path: Path, expected: tuple[int, ...]) -> bytes:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            if _fingerprint(os.fstat(stream.fileno())) != expected:
                raise WorkspaceError("Workspace changed during snapshot")
            content = stream.read(self.max_bytes + 1)
            if len(content) > self.max_bytes or _fingerprint(os.fstat(stream.fileno())) != expected:
                raise WorkspaceError("Workspace changed during snapshot")
        return content

    def _capture(self, root: Path) -> tuple[tuple[WorkspaceEntry, ...], dict[str, tuple[int, ...]]]:
        before = self._inventory(root)
        entries = []
        for name, fingerprint in sorted(before.items()):
            if name == ".":
                continue
            directory = stat.S_ISDIR(fingerprint[2])
            data = b"" if directory else self._read_file(root / name, fingerprint)
            entries.append(WorkspaceEntry(name, directory, stat.S_IMODE(fingerprint[2]), data,
                                          "" if directory else hashlib.sha256(data).hexdigest()))
        if self._inventory(root) != before:
            raise WorkspaceError("Workspace changed during snapshot")
        return tuple(entries), before

    def copy_asset(self, source: str | Path, destination: str | Path) -> Path:
        """Copy a declared static file or directory without following links."""
        self._check_root()
        if self.assets_root is None:
            raise WorkspaceError("An explicit assets_root is required")
        asset_info = _inspect(self.assets_root)
        if (asset_info.st_dev, asset_info.st_ino) != self._assets_identity:
            raise WorkspaceError("Assets root was replaced")
        origin = self._target(source, base=self.assets_root)
        target = self._target(destination)
        info = _inspect(origin)
        if stat.S_ISREG(info.st_mode):
            if info.st_size > self.max_bytes:
                raise WorkspaceError("Asset exceeds the byte limit")
            fingerprint = _fingerprint(info)
            data = self._read_file(origin, fingerprint)
            if _fingerprint(_inspect(origin)) != fingerprint:
                raise WorkspaceError("Asset changed during copy")
            self.write_bytes(destination, data)
            target.chmod(stat.S_IMODE(info.st_mode))
            return target
        entries, before = self._capture(origin)
        destination_relative = PurePosixPath(_relative(destination).as_posix())
        # Validate the entire source and target before writing any contents.
        for entry in entries:
            self._target((destination_relative / entry.path).as_posix())
        if self._inventory(origin) != before:
            raise WorkspaceError("Asset changed during copy")
        target.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            relative = (destination_relative / entry.path).as_posix()
            if entry.is_directory:
                self._target(relative).mkdir(parents=True, exist_ok=True)
            else:
                self.write_bytes(relative, entry.content)
        for entry in sorted(entries, key=lambda item: len(Path(item.path).parts), reverse=True):
            self._target((destination_relative / entry.path).as_posix()).chmod(entry.mode)
        target.chmod(stat.S_IMODE(info.st_mode))
        return target

    def snapshot(self) -> WorkspaceSnapshot:
        """Capture bounded files, empty directories and supported permissions."""
        self._check_root()
        entries, inventory = self._capture(self.root)
        self._check_root()
        return WorkspaceSnapshot(self.root, self._identity, stat.S_IMODE(inventory["."][2]), entries)

    def _validate_snapshot(self, snapshot: WorkspaceSnapshot) -> None:
        self._check_root()
        if snapshot.root != self.root or snapshot.root_identity != self._identity:
            raise WorkspaceError("Snapshot belongs to a different workspace")
        names: set[str] = set()
        total = 0
        for entry in snapshot.entries:
            if _relative(entry.path).as_posix() != entry.path or entry.path in names:
                raise WorkspaceError("Snapshot contains invalid or duplicate paths")
            names.add(entry.path)
            if not 0 <= entry.mode <= 0o7777:
                raise WorkspaceError("Snapshot permission mode is invalid")
            if entry.is_directory:
                if entry.content or entry.sha256:
                    raise WorkspaceError("Snapshot directory contains file data")
            elif hashlib.sha256(entry.content).hexdigest() != entry.sha256:
                raise WorkspaceError("Snapshot file checksum is invalid")
            total += len(entry.content)
        directory_names = {entry.path for entry in snapshot.entries if entry.is_directory}
        for entry in snapshot.entries:
            parent = PurePosixPath(entry.path).parent
            if str(parent) != "." and str(parent) not in directory_names:
                raise WorkspaceError("Snapshot is missing a parent directory")
        if len(names) > self.max_files or total > self.max_bytes:
            raise WorkspaceError("Snapshot exceeds workspace limits")
        if not 0 <= snapshot.root_mode <= 0o7777:
            raise WorkspaceError("Snapshot root permission mode is invalid")

    def diff(self, snapshot: WorkspaceSnapshot) -> WorkspaceDiff:
        """Compare contents, entry kinds and modes, not incidental timestamps."""
        self._validate_snapshot(snapshot)
        before = {entry.path: entry for entry in snapshot.entries}
        current = self.snapshot()
        after = {entry.path: entry for entry in current.entries}
        modified = {key for key in before.keys() & after.keys() if before[key] != after[key]}
        if current.root_mode != snapshot.root_mode:
            modified.add(".")
        return WorkspaceDiff(tuple(sorted(after.keys() - before.keys())), tuple(sorted(modified)),
                             tuple(sorted(before.keys() - after.keys())))

    def restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Restore only this workspace; callers must stop all workspace writers first.

        Errors are explicit and may leave a partially restored workspace. This is
        not a filesystem transaction; a successful return includes a full diff check.
        """
        self._validate_snapshot(snapshot)
        before = self._inventory(self.root)
        if self._inventory(self.root) != before:
            raise WorkspaceError("Workspace changed before restore")
        # Test-created read-only entries still belong to this disposable workspace.
        # Make them writable before restoration, keeping the snapshot's final modes.
        for name, fingerprint in list(before.items()):
            self._check_root()
            path = self.root if name == "." else self._target(name)
            info = _inspect(path)
            if _fingerprint(info) != fingerprint:
                raise WorkspaceError("Workspace changed during restore")
            mode = stat.S_IMODE(info.st_mode) | stat.S_IWUSR
            if stat.S_ISDIR(info.st_mode):
                mode |= stat.S_IXUSR
            path.chmod(mode)
            before[name] = _fingerprint(_inspect(path))
        expected = {entry.path: entry for entry in snapshot.entries}
        # Remove new entries and kind conflicts, checking each object before removal.
        for name in sorted((name for name in before if name != "."),
                           key=lambda name: len(Path(name).parts), reverse=True):
            self._check_root()
            path = self._target(name)
            info = _inspect(path)
            if (info.st_dev, info.st_ino, info.st_mode) != before[name][:3]:
                raise WorkspaceError("Workspace changed during restore")
            entry = expected.get(name)
            directory = stat.S_ISDIR(info.st_mode)
            if entry is None or entry.is_directory != directory:
                if directory:
                    path.rmdir()
                else:
                    if _fingerprint(info) != before[name]:
                        raise WorkspaceError("Workspace changed during restore")
                    path.unlink()
        for entry in sorted(snapshot.entries, key=lambda item: len(Path(item.path).parts)):
            self._check_root()
            path = self._target(entry.path)
            if entry.is_directory:
                path.mkdir(parents=True, exist_ok=True)
            else:
                if path.exists() and entry.path in before:
                    if _fingerprint(_inspect(path)) != before[entry.path]:
                        raise WorkspaceError("Workspace changed during restore")
                self.write_bytes(entry.path, entry.content)
        for entry in sorted(snapshot.entries, key=lambda item: len(Path(item.path).parts), reverse=True):
            self._target(entry.path).chmod(entry.mode)
        self.root.chmod(snapshot.root_mode)
        changes = self.diff(snapshot)
        if changes.added or changes.modified or changes.deleted:
            raise WorkspaceError("Workspace verification failed after restore")

    @contextmanager
    def rollback(self) -> Iterator[WorkspaceSnapshot]:
        """Always restore the captured state and preserve any cleanup failure."""
        snapshot = self.snapshot()
        try:
            yield snapshot
        except BaseException as original:
            try:
                self.restore(snapshot)
            except BaseException as cleanup:
                raise BaseExceptionGroup("Workspace operation and rollback both failed", [original, cleanup])
            raise
        else:
            self.restore(snapshot)
