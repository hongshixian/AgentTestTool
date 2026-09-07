"""Verify bounded workspace preparation, snapshots, and restoration."""

from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path, PureWindowsPath
import stat
import tempfile

import pytest

from agent_models.environment.workspace import WorkspaceDiff, WorkspaceError, WorkspaceManager


def test_write_snapshot_diff_restore_preserves_empty_directories(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_text("nested/message.txt", "原始内容")
    manager.write_bytes("bytes.bin", b"\x00\xff")
    (manager.root / "empty").mkdir()
    original = manager.snapshot()
    manager.write_text("nested/message.txt", "changed")
    (manager.root / "bytes.bin").unlink()
    manager.write_text("extra/new.txt", "new")
    assert manager.diff(original) == WorkspaceDiff(
        ("extra", "extra/new.txt"), ("nested/message.txt",), ("bytes.bin",)
    )
    manager.restore(original)
    assert manager.diff(original) == WorkspaceDiff((), (), ())
    assert (manager.root / "nested/message.txt").read_text() == "原始内容"
    assert (manager.root / "empty").is_dir()


def test_snapshot_is_immutable_and_independent(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_bytes("a", b"original")
    original = manager.snapshot()
    manager.write_bytes("a", b"new")
    assert original.entries[0].content == b"original"
    with pytest.raises(FrozenInstanceError):
        original.entries[0].content = b"corrupt"
    with pytest.raises(WorkspaceError, match="checksum"):
        manager.restore(replace(original, entries=(replace(original.entries[0], content=b"bad"),)))
    assert (manager.root / "a").read_bytes() == b"new"


@pytest.mark.parametrize("path", ["../outside", "/absolute", "a/../../outside", "", ".", "C:/bad", "a\\bad", "file:stream", "NUL", "name.", "name "])
def test_rejects_nonportable_and_escaping_paths(tmp_path: Path, path: str) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    with pytest.raises(WorkspaceError):
        manager.write_text(path, "no")


def test_refuses_broad_roots_and_git_repositories(tmp_path: Path) -> None:
    for root in (Path.cwd(), Path.home(), Path(Path.cwd().anchor), Path(tempfile.gettempdir())):
        with pytest.raises(WorkspaceError, match="root"):
            WorkspaceManager(root)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    with pytest.raises(WorkspaceError, match="root"):
        WorkspaceManager(repo)


def test_refuses_foreign_and_replaced_root(tmp_path: Path) -> None:
    first = WorkspaceManager(tmp_path / "first")
    second = WorkspaceManager(tmp_path / "second")
    snapshot = first.snapshot()
    with pytest.raises(WorkspaceError, match="different workspace"):
        second.restore(snapshot)
    first.root.rename(tmp_path / "old")
    first.root.mkdir()
    with pytest.raises(WorkspaceError, match="replaced"):
        first.restore(snapshot)


def _symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links require platform support and appropriate permissions")


def test_rejects_symlink_on_snapshot_write_and_restore(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious").write_text("preserve")
    manager = WorkspaceManager(tmp_path / "workspace")
    snapshot = manager.snapshot()
    _symlink(outside, manager.root / "escape")
    for operation in (manager.snapshot, lambda: manager.write_text("escape/precious", "bad"),
                      lambda: manager.restore(snapshot)):
        with pytest.raises(WorkspaceError, match="links"):
            operation()
    assert (outside / "precious").read_text() == "preserve"


def test_rejects_symlink_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    _symlink(real, link)
    with pytest.raises(WorkspaceError, match="root"):
        WorkspaceManager(link)


def test_rejects_hardlinks_without_modifying_target(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    source = tmp_path / "outside"
    source.write_text("preserve")
    try:
        os.link(source, manager.root / "link")
    except OSError:
        pytest.skip("Hard links are not available on this filesystem")
    with pytest.raises(WorkspaceError, match="hard-linked"):
        manager.write_text("link", "bad")
    with pytest.raises(WorkspaceError, match="hard-linked"):
        manager.snapshot()
    assert source.read_text() == "preserve"


def test_rejects_posix_fifo_before_opening_it(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO support is required")
    manager = WorkspaceManager(tmp_path / "workspace")
    os.mkfifo(manager.root / "fifo")
    with pytest.raises(WorkspaceError, match="special"):
        manager.snapshot()


def test_copies_assets_templates_and_empty_directories(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    (assets / "template/empty").mkdir(parents=True)
    (assets / "template/example.txt").write_text("template")
    manager = WorkspaceManager(tmp_path / "workspace", assets)
    manager.copy_asset("template", "project")
    manager.copy_asset("template/example.txt", "single.txt")
    assert (manager.root / "project/empty").is_dir()
    assert (manager.root / "project/example.txt").read_text() == "template"
    assert (manager.root / "single.txt").read_text() == "template"
    assert (assets / "template/example.txt").read_text() == "template"


def test_windows_relative_paths_copy_nested_template_without_windows_host(tmp_path: Path, monkeypatch) -> None:
    assets = tmp_path / "assets"
    (assets / "templates/project/empty").mkdir(parents=True)
    (assets / "templates/project/nested").mkdir()
    (assets / "templates/project/nested/input.txt").write_text("fixture")
    manager = WorkspaceManager(tmp_path / "workspace", assets)
    # PureWindowsPath reproduces native Windows separators on every host.
    source = PureWindowsPath("templates") / "project"
    destination = PureWindowsPath("prepared") / "project"
    assert "\\" in str(destination)
    target = manager._target
    paths = []

    def observe(relative, **kwargs):
        paths.append(relative)
        return target(relative, **kwargs)

    monkeypatch.setattr(manager, "_target", observe)
    manager.copy_asset(source, destination)
    # Every internally joined path remains a portable string, not a native Path
    # whose string form would change to backslashes on Windows.
    assert paths[:2] == [source, destination]
    assert paths[2:] and all(isinstance(path, str) and "\\" not in path for path in paths[2:])
    assert (manager.root / "prepared/project/nested/input.txt").read_text() == "fixture"
    assert (manager.root / "prepared/project/empty").is_dir()
    manager.write_text(PureWindowsPath("prepared") / "extra.txt", "extra")
    assert (manager.root / "prepared/extra.txt").read_text() == "extra"
    with pytest.raises(WorkspaceError):
        manager.copy_asset("templates/project", "prepared\\unsafe")
    with pytest.raises(WorkspaceError):
        manager.write_text(PureWindowsPath("..") / "outside", "bad")
    with pytest.raises(WorkspaceError):
        manager.write_text(PureWindowsPath("C:/outside"), "bad")


def test_asset_validation_happens_before_copy(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    (assets / "template").mkdir(parents=True)
    (assets / "template/okay").write_text("ok")
    _symlink(tmp_path / "missing", assets / "template/link")
    manager = WorkspaceManager(tmp_path / "workspace", assets)
    with pytest.raises(WorkspaceError, match="links"):
        manager.copy_asset("template", "project")
    assert not (manager.root / "project").exists()
    with pytest.raises(WorkspaceError):
        manager.copy_asset("../outside", "project")
    with pytest.raises(WorkspaceError, match="explicit"):
        WorkspaceManager(tmp_path / "other").copy_asset("sample", "sample")


def test_asset_roots_cannot_overlap_workspace(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    with pytest.raises(WorkspaceError, match="overlap"):
        WorkspaceManager(assets / "workspace", assets)


def test_snapshot_limits_are_checked_before_reading_all_data(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace", max_files=1, max_bytes=4)
    with pytest.raises(WorkspaceError, match="byte limit"):
        manager.write_bytes("large", b"12345")
    (manager.root / "large").write_bytes(b"12345")
    with pytest.raises(WorkspaceError, match="byte limit"):
        manager.snapshot()
    (manager.root / "large").unlink()
    manager.write_text("one", "1")
    manager.write_text("two", "2")
    with pytest.raises(WorkspaceError, match="entry count"):
        manager.snapshot()


def test_detects_concurrent_change_during_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_text("input", "initial")
    read = manager._read_file

    def mutate(path: Path, fingerprint: tuple[int, ...]) -> bytes:
        content = read(path, fingerprint)
        path.write_text("concurrent change")
        return content

    monkeypatch.setattr(manager, "_read_file", mutate)
    with pytest.raises(WorkspaceError, match="changed"):
        manager.snapshot()


def test_detects_concurrent_change_before_restore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_text("input", "initial")
    original = manager.snapshot()
    inventory = manager._inventory
    called = 0

    def mutate(root: Path) -> dict[str, tuple[int, ...]]:
        nonlocal called
        result = inventory(root)
        called += 1
        if called == 1:
            (root / "input").write_text("concurrent change")
        return result

    monkeypatch.setattr(manager, "_inventory", mutate)
    with pytest.raises(WorkspaceError, match="changed"):
        manager.restore(original)
    assert (manager.root / "input").read_text() == "concurrent change"


def test_restore_handles_file_directory_kind_changes(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_text("original_file", "file")
    manager.write_text("original_dir/child", "child")
    original = manager.snapshot()
    (manager.root / "original_file").unlink()
    manager.write_text("original_file/new", "new")
    (manager.root / "original_dir/child").unlink()
    (manager.root / "original_dir").rmdir()
    manager.write_text("original_dir", "changed")
    manager.restore(original)
    assert manager.diff(original) == WorkspaceDiff((), (), ())


def test_restores_supported_file_modes(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    file = manager.write_text("script", "example")
    file.chmod(0o700)
    original = manager.snapshot()
    manager.write_text("script", "changed")
    manager.restore(original)
    assert stat.S_IMODE(file.stat().st_mode) == original.entries[0].mode


def test_restore_handles_read_only_entries_and_test_created_repository(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    directory = manager.root / "readonly"
    directory.mkdir()
    manager.write_text("readonly/original", "before")
    directory.chmod(0o500)
    original = manager.snapshot()
    directory.chmod(0o700)
    manager.write_text("readonly/new", "new").chmod(0o400)
    directory.chmod(0o500)
    manager.write_text(".git/config", "fake test repository configuration")
    manager.restore(original)
    assert not (manager.root / ".git").exists()
    assert manager.diff(original) == WorkspaceDiff((), (), ())
    directory.chmod(0o700)


def test_rollback_restores_success_and_body_failure(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")
    manager.write_text("value", "before")
    with manager.rollback():
        manager.write_text("value", "during")
    assert (manager.root / "value").read_text() == "before"
    with pytest.raises(ValueError, match="body failed"):
        with manager.rollback():
            manager.write_text("value", "during")
            raise ValueError("body failed")
    assert (manager.root / "value").read_text() == "before"


def test_rollback_exposes_cleanup_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WorkspaceManager(tmp_path / "workspace")

    def fail(snapshot: object) -> None:
        raise WorkspaceError("cleanup failed")

    monkeypatch.setattr(manager, "restore", fail)
    with pytest.raises(WorkspaceError, match="cleanup failed"):
        with manager.rollback():
            pass
    with pytest.raises(ExceptionGroup) as caught:
        with manager.rollback():
            raise ValueError("body failed")
    assert [type(item) for item in caught.value.exceptions] == [ValueError, WorkspaceError]
