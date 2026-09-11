"""Bound subprocess lifetimes, including independently sessioned descendants."""

from __future__ import annotations

import subprocess
import time
import os
import signal
from contextlib import nullcontext
from typing import Any, Sequence

import psutil

from agent_models.windows_job import WindowsJobError, WindowsProcessJob


class ProcessCleanupError(RuntimeError):
    """A worker may still own processes; its resources must not be restored."""


def _remember_children(root: psutil.Process, known: set[psutil.Process]) -> None:
    try:
        known.update(root.children(recursive=True))
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied as exc:
        raise ProcessCleanupError("Cannot inspect worker process tree") from exc


def _stop_processes(processes: set[psutil.Process]) -> None:
    failed = False
    for process in processes:
        try:
            process.suspend()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            failed = True
    for process in list(processes):
        try:
            _remember_children(process, processes)
        except ProcessCleanupError:
            failed = True
    for process in processes:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            failed = True
    _, alive = psutil.wait_procs(list(processes), timeout=5)
    for process in alive:
        try:
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                raise ProcessCleanupError("Worker descendants did not stop")
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            failed = True
    if failed:
        raise ProcessCleanupError("Cannot confirm worker process tree termination")


def _stop_group(group_id: int | None) -> None:
    if group_id is None:
        return
    try:
        os.killpg(group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        raise ProcessCleanupError("Cannot terminate worker process group") from exc


def run_managed_process(
    command: Sequence[str], *, timeout: float, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run a pytest worker, tracking descendants even if they create sessions.

    Unlike subprocess.run, a phase timeout also stops tracked CLI/MCP children.
    Callers must not reuse worker resources after ProcessCleanupError.
    """
    grouped = hasattr(os, "killpg")
    try:
        with nullcontext(None) if grouped else WindowsProcessJob() as job:
            return _run_process(command, timeout=timeout, job=job, **kwargs)
    except WindowsJobError as error:
        raise ProcessCleanupError(str(error)) from error


def _run_process(
    command: Sequence[str], *, timeout: float,
    job: WindowsProcessJob | None, **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    kwargs.pop("check", None)
    capture = kwargs.pop("capture_output", False)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if job is None:
        kwargs["start_new_session"] = True
    else:
        # CREATE_SUSPENDED prevents children escaping before Job assignment.
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x00000004
    process = subprocess.Popen(tuple(command), **kwargs)
    group_id = process.pid if job is None else None
    try:
        root = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        _stop_group(group_id)
        stdout, stderr = process.communicate(timeout=5)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except psutil.Error as error:
        try:
            _stop_group(group_id)
            process.kill()
            process.wait(timeout=5)
        finally:
            raise ProcessCleanupError("Cannot establish worker process tracking") from error
    descendants: set[psutil.Process] = set()
    deadline = time.monotonic() + timeout
    try:
        if job is not None:
            job.attach(process.pid)
            root.resume()
        while True:
            _remember_children(root, descendants)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    raise
    except BaseException:
        try:
            _remember_children(root, descendants)
        finally:
            # Also catch short-lived parents whose ordinary children were reparented.
            _stop_group(group_id)
            _stop_processes({root, *descendants})
        process.wait(timeout=5)
        raise
    _stop_group(group_id)
    _stop_processes(descendants)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
