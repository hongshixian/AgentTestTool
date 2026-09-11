"""Check Windows Job Object setup, assignment and cleanup with an offline API."""

from types import SimpleNamespace

import pytest

from agent_models import windows_job


class Function:
    def __init__(self, name, calls, result=1):
        self.name = name
        self.calls = calls
        self.result = result

    def __call__(self, *args):
        self.calls.append((self.name, args))
        return self.result


@pytest.fixture
def api(monkeypatch):
    calls = []
    api = SimpleNamespace(**{
        name: Function(name, calls)
        for name in (
            "CreateJobObjectW", "SetInformationJobObject", "OpenProcess",
            "AssignProcessToJobObject", "TerminateJobObject", "QueryInformationJobObject",
            "CloseHandle",
        )
    })
    monkeypatch.setattr(windows_job.ctypes, "WinDLL", lambda *args, **kwargs: api, raising=False)
    api.calls = calls
    return api


def test_job_is_configured_attached_and_confirmed_empty_before_close(api):
    with windows_job.WindowsProcessJob() as job:
        job.attach(1234)
    names = [name for name, _ in api.calls]
    assert names == [
        "CreateJobObjectW", "SetInformationJobObject", "OpenProcess",
        "AssignProcessToJobObject", "CloseHandle", "TerminateJobObject",
        "QueryInformationJobObject", "CloseHandle",
    ]
    limit_call = api.calls[1][1]
    assert limit_call[1] == 9
    assert limit_call[2]._obj.BasicLimitInformation.LimitFlags == 0x2000
    assert api.calls[2][1] == (0x0101, False, 1234)


def test_assignment_failure_does_not_silently_run_without_containment(api):
    api.AssignProcessToJobObject.result = 0
    with pytest.raises(windows_job.WindowsJobError, match="assign"):
        with windows_job.WindowsProcessJob() as job:
            job.attach(1234)
    assert api.calls[-1][0] == "CloseHandle"


def test_unverifiable_job_cleanup_raises_instead_of_claiming_success(api):
    api.QueryInformationJobObject.result = 0
    with pytest.raises(windows_job.WindowsJobError, match="inspect"):
        with windows_job.WindowsProcessJob():
            pass
    assert api.calls[-1][0] == "CloseHandle"


def test_configuration_failure_closes_created_job_handle(api):
    api.SetInformationJobObject.result = 0
    with pytest.raises(windows_job.WindowsJobError, match="configure"):
        windows_job.WindowsProcessJob()
    assert api.calls[-1][0] == "CloseHandle"
