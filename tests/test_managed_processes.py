"""Verify bounded cleanup of worker descendants across process sessions."""

import subprocess
import sys
import os

import psutil
import pytest

from agent_models.processes import run_managed_process


def test_managed_process_collects_output():
    result = run_managed_process(
        [sys.executable, "-c", "print('finished')"], timeout=5,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "finished"


def test_timeout_stops_child_in_separate_session(tmp_path):
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess, sys, time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], "
        "start_new_session=True); "
        f"Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(60)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        run_managed_process(
            [sys.executable, "-c", script], timeout=1,
            capture_output=True, text=True,
        )
    pid = int(pid_file.read_text())
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="POSIX process group regression")
def test_fast_parent_exit_does_not_leave_inherited_group_child():
    script = (
        "import subprocess, sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print(child.pid)"
    )
    result = run_managed_process(
        [sys.executable, "-c", script], timeout=5, capture_output=True, text=True,
    )
    pid = int(result.stdout.strip())
    try:
        _, alive = psutil.wait_procs([psutil.Process(pid)], timeout=3)
        assert all(proc.status() == psutil.STATUS_ZOMBIE for proc in alive)
    except psutil.NoSuchProcess:
        pass
    finally:
        if psutil.pid_exists(pid):
            psutil.Process(pid).kill()
