"""Create private, disposable CodeBuddy profiles for isolated pytest workers."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Iterator

from agent_models.processes import ProcessCleanupError


def _copy_profile(source: Path, target: Path) -> None:
    for entry in source.iterdir():
        mode = entry.lstat().st_mode
        destination = target / entry.name
        if stat.S_ISDIR(mode):
            destination.mkdir(mode=0o700)
            _copy_profile(entry, destination)
        elif stat.S_ISREG(mode):
            # Do not retain group/world-readable permissions from the source.
            with entry.open("rb") as reader, destination.open("xb") as writer:
                destination.chmod(0o600)
                shutil.copyfileobj(reader, writer)
        else:
            raise ValueError("Worker profile source contains a symlink or special file")


@contextmanager
def isolated_worker_profile() -> Iterator[dict[str, str]]:
    """Copy an explicit test profile; never fall back to the personal profile.

    The caller must stop the worker and all its children before leaving this
    context. Configuration includes credentials, so it lives outside artifacts.
    This isolates local state, not the remote account or the OS filesystem.
    """
    configured = os.environ.get("CODEBUDDY_CONFIG_DIR", "").strip()
    if not configured:
        raise ValueError("Parallel CodeBuddy workers require a dedicated test profile")
    source = Path(configured).expanduser()
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Dedicated CodeBuddy test profile must be an existing directory")
    temporary = Path(tempfile.mkdtemp(prefix="agent-test-worker-"))
    cleanup_safe = True
    try:
        target = Path(temporary) / "profile"
        if target.resolve().is_relative_to(source.resolve()):
            raise ValueError("Worker temporary directory must be outside the source profile")
        target.mkdir(mode=0o700)
        _copy_profile(source, target)
        yield {"CODEBUDDY_CONFIG_DIR": str(target)}
    except ProcessCleanupError:
        cleanup_safe = False
        raise
    finally:
        if cleanup_safe:
            shutil.rmtree(temporary)
