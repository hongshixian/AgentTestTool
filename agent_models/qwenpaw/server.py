"""Own one isolated QwenPaw app process: headless bootstrap, readiness and teardown."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import psutil

from agent_models.processes import (
    ProcessCleanupError,
    _remember_children,
    _stop_processes,
    run_managed_process,
)
from agent_models.qwenpaw.client import QwenPawApiError, QwenPawClient
from agent_models.qwenpaw.profile import QwenPawTestProfile
from agent_models.windows_job import WindowsProcessJob
from configs.environment import agent_process_environment

_VERSION = re.compile(r"version\s+(\d+(?:\.\d+)+\S*)", re.IGNORECASE)
_CLI_TIMEOUT = 120.0
_READY_TIMEOUT = 120.0


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def resolve_executable(executable: str) -> str | None:
    path = Path(executable).expanduser()
    if path.is_absolute() or os.sep in executable:
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(executable)


def installed_version(executable: str, *, environment: dict[str, str] | None = None) -> str | None:
    """Return the version printed by ``qwenpaw --version`` (last matching line)."""
    result = run_managed_process(
        (executable, "--version"), timeout=_CLI_TIMEOUT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
        env=environment if environment is not None else agent_process_environment(),
    )
    matches = _VERSION.findall(result.stdout + "\n" + result.stderr)
    return matches[-1] if result.returncode == 0 and matches else None


class QwenPawServer:
    """One QwenPaw instance with private working, secret and project directories.

    The working and secret directories live outside the evaluator workspace so
    product state never appears in workspace snapshots. Isolation is a separate
    configuration, not an OS sandbox.
    """

    def __init__(self, profile: QwenPawTestProfile, *, executable: str) -> None:
        self.profile = profile
        self.executable = executable
        self._root = Path(tempfile.mkdtemp(prefix="ats-qwenpaw-"))
        self.working_dir = self._root / "work"
        self.secret_dir = self._root / "secret"
        self.log_path = self._root / "app.log"
        self.port = 0
        self.client: QwenPawClient | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._job: WindowsProcessJob | None = None
        self._closed = False

    @property
    def root(self) -> Path:
        return self._root

    def _environment(self) -> dict[str, str]:
        environment = agent_process_environment()
        for name in ("QWENPAW_TEST_API_KEY", "IIIS_API_KEY"):
            environment.pop(name, None)
        environment.update({
            "QWENPAW_WORKING_DIR": str(self.working_dir),
            "QWENPAW_SECRET_DIR": str(self.secret_dir),
            "PYTHONIOENCODING": "utf-8",
        })
        return environment

    def _cli(self, *arguments: str) -> None:
        result = run_managed_process(
            (self.executable, *arguments), timeout=_CLI_TIMEOUT, cwd=self._root,
            env=self._environment(), capture_output=True, text=True, encoding="utf-8",
            errors="replace", stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            tail = (result.stderr or result.stdout)[-400:]
            raise RuntimeError(f"qwenpaw {arguments[0]} {arguments[1] if len(arguments) > 1 else ''} "
                               f"exited {result.returncode}: {tail}")

    def start(self, *, agent_settings: dict[str, Any] | None = None) -> QwenPawClient:
        """Bootstrap headlessly; ``agent_settings`` are written to the default agent before launch.

        Changing ``approval_level`` or ``project_dir`` through REST after launch triggers an
        asynchronous agent reload that can orphan MCP drivers registered meanwhile.
        """
        if self._closed:
            raise RuntimeError("QwenPaw server was already closed")
        if self.client is not None:
            return self.client
        if not self.profile.api_key:
            raise RuntimeError("QwenPaw test API key is not configured (QWENPAW_TEST_API_KEY or IIIS_API_KEY)")
        self.working_dir.mkdir(mode=0o700)
        self.secret_dir.mkdir(mode=0o700)
        self._cli("init", "--defaults", "--accept-security")
        self._cli("models", "add-provider", self.profile.provider_id,
                  "--name", self.profile.provider_name, "--base-url", self.profile.base_url)
        self._cli("models", "add-model", self.profile.provider_id,
                  "--model-id", self.profile.model, "--model-name", self.profile.model)
        if agent_settings:
            agent_file = self.working_dir / "workspaces" / "default" / "agent.json"
            config = json.loads(agent_file.read_text(encoding="utf-8"))
            config.update(agent_settings)
            agent_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self.port = _unused_loopback_port()
        command = (self.executable, "app", "--host", "127.0.0.1", "--port", str(self.port))
        with self.log_path.open("wb") as log:
            if os.name == "nt":
                # Suspend until assigned to a kill-on-close Job; MCP children cannot escape.
                self._job = WindowsProcessJob()
                options: dict[str, Any] = {"creationflags": 0x00000004}
            else:
                options = {"start_new_session": True}
            self._process = subprocess.Popen(command, cwd=self._root, env=self._environment(),
                                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                             **options)
        if self._job is not None:
            self._job.attach(self._process.pid)
            psutil.Process(self._process.pid).resume()
        client = QwenPawClient(f"http://127.0.0.1:{self.port}")
        self._await_ready(client)
        client.put(f"/api/models/{self.profile.provider_id}/config", {"api_key": self.profile.api_key})
        client.put("/api/models/active", {"provider_id": self.profile.provider_id,
                                          "model": self.profile.model, "scope": "global"})
        self.client = client
        return client

    def _await_ready(self, client: QwenPawClient) -> None:
        deadline = time.monotonic() + _READY_TIMEOUT
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(f"QwenPaw app exited with {self._process.returncode} during startup")
            try:
                version = client.version(timeout=3.0)
            except QwenPawApiError:
                time.sleep(0.5)
                continue
            if version != self.profile.expected_version:
                raise RuntimeError(f"QwenPaw reports version {version}, expected {self.profile.expected_version}")
            return
        raise TimeoutError("QwenPaw app did not become ready")

    def log_tail(self, limit: int = 2000) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return ""

    def close(self) -> None:
        """Stop the app and its MCP children before removing private state."""
        if self._closed:
            return
        self._closed = True
        process = self._process
        if self._job is not None:
            try:
                self._job.__exit__(None, None, None)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        elif process is not None:
            _stop_posix_group(process)
        shutil.rmtree(self._root, ignore_errors=True)


def _live_group_members(group_id: int) -> bool:
    for process in psutil.process_iter(attrs=["status"]):
        try:
            if process.info["status"] != psutil.STATUS_ZOMBIE and os.getpgid(process.pid) == group_id:
                return True
        except (ProcessLookupError, psutil.NoSuchProcess):
            continue
        except (PermissionError, psutil.AccessDenied) as error:
            raise ProcessCleanupError("Cannot inspect QwenPaw process group") from error
    return False


def _stop_posix_group(process: subprocess.Popen[Any]) -> None:
    group_id = process.pid  # start_new_session=True makes the app a group leader.
    descendants: set[psutil.Process] = set()
    try:
        _remember_children(psutil.Process(group_id), descendants)
    except psutil.NoSuchProcess:
        pass
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        if process.poll() is not None and not _live_group_members(group_id):
            break
        try:
            os.killpg(group_id, sig)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            raise ProcessCleanupError("Cannot signal QwenPaw process group") from error
        try:
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            continue
    if process.poll() is None:
        raise ProcessCleanupError("QwenPaw app did not exit")
    if descendants:
        _stop_processes(descendants)
    deadline = time.monotonic() + 5
    while _live_group_members(group_id):
        if time.monotonic() >= deadline:
            raise ProcessCleanupError("QwenPaw process group still has live children")
        time.sleep(0.05)
