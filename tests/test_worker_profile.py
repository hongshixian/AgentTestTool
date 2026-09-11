"""Verify disposable worker configuration without real credentials or services."""

from pathlib import Path
import tempfile

import pytest

from agent_models.codebuddy.worker_profile import isolated_worker_profile
from agent_models.processes import ProcessCleanupError


def test_profiles_are_separate_and_cleanup_preserves_source(tmp_path, monkeypatch):
    source = tmp_path / "dedicated"
    source.mkdir()
    (source / "config.json").write_text('{"token": "invalid-test-token"}')
    (source / "rules").mkdir()
    (source / "rules" / "test.md").write_text("baseline")
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(source))
    with isolated_worker_profile() as first, isolated_worker_profile() as second:
        first_path = Path(first["CODEBUDDY_CONFIG_DIR"])
        second_path = Path(second["CODEBUDDY_CONFIG_DIR"])
        assert first_path != second_path != source
        (first_path / "rules" / "test.md").write_text("changed")
        assert (second_path / "rules" / "test.md").read_text() == "baseline"
        assert (source / "rules" / "test.md").read_text() == "baseline"
    assert not first_path.exists()
    assert not second_path.exists()
    assert (source / "config.json").is_file()


def test_profile_removed_when_worker_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="worker failed"):
        with isolated_worker_profile() as environment:
            path = Path(environment["CODEBUDDY_CONFIG_DIR"])
            raise RuntimeError("worker failed")
    assert not path.exists()


@pytest.mark.parametrize("configured", [None, "missing-profile"])
def test_no_personal_profile_fallback(tmp_path, monkeypatch, configured):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CODEBUDDY_CONFIG_DIR", raising=False)
    if configured is not None:
        monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", configured)
    with pytest.raises(ValueError):
        with isolated_worker_profile():
            pytest.fail("Invalid dedicated profile was accepted")


def test_symlink_cannot_copy_files_outside_dedicated_profile(tmp_path, monkeypatch):
    source = tmp_path / "dedicated"
    source.mkdir()
    external = tmp_path / "unrelated"
    external.write_text("must not be copied")
    try:
        (source / "link").symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is unavailable on this platform")
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(source))
    with pytest.raises(ValueError, match="symlink or special"):
        with isolated_worker_profile():
            pytest.fail("Symlink was accepted")


def test_temporary_directory_cannot_recurse_into_source(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with pytest.raises(ValueError, match="outside the source"):
        with isolated_worker_profile():
            pytest.fail("Recursive profile copy was accepted")
    assert list(tmp_path.iterdir()) == []


def test_unconfirmed_process_cleanup_retains_private_profile(tmp_path, monkeypatch):
    source = tmp_path / "dedicated"
    source.mkdir()
    scratch = tmp_path / "worker-profiles"
    scratch.mkdir()
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(source))
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    with pytest.raises(ProcessCleanupError):
        with isolated_worker_profile() as environment:
            retained = Path(environment["CODEBUDDY_CONFIG_DIR"])
            raise ProcessCleanupError("simulated live descendant")
    assert retained.is_dir()
    assert retained.is_relative_to(scratch)
