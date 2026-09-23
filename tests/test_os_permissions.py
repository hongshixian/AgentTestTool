"""Offline quality and boundary tests for hypothetical native OS event sources."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from evidence_collectors.base import (
    CollectionCheckpoint,
    CollectionContext,
    CollectorHealth,
    CollectorHealthState,
    CollectorStatus,
    ObservationWindow,
)
from evidence_collectors.os_permissions import (
    OSAccessVerdict,
    OSPermissionAccess,
    OSPermissionAction,
    OSPermissionCollector,
    OSPermissionCoverage,
    OSPermissionRead,
    OSPermissionSourceInfo,
    OSProcessIdentity,
    assess_no_unauthorized_os_access,
)


PROCESS = OSProcessIdentity(pid=42, instance_id="synthetic-process-start-token")
NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


def _event(
    sequence: int, task_id: str, phase: str,
    *, action: OSPermissionAction = OSPermissionAction.GRANTED,
    process: OSProcessIdentity = PROCESS,
) -> OSPermissionAccess:
    return OSPermissionAccess(
        sequence, "run-synthetic", task_id, phase, "microphone", process, action, NOW,
    )


def _coverage(
    task_id: str, phase: str, *, process: OSProcessIdentity = PROCESS,
    complete: bool = True, task_finished: bool = True,
    process_tree_complete: bool = True,
) -> OSPermissionCoverage:
    return OSPermissionCoverage(
        "run-synthetic", task_id, phase, "microphone", process,
        complete, task_finished, process_tree_complete,
    )


class SyntheticOSSource:
    """In-memory unit-test stand-in; NOT an OS adapter or production evidence."""

    def __init__(self) -> None:
        self.info = OSPermissionSourceInfo(
            "synthetic-source", True, True, frozenset({"microphone"}),
        )
        self.reads: dict[tuple[int, int], OSPermissionRead] = {
            (0, 1): OSPermissionRead(
                (_event(1, "control", "positive_control"),),
                (_coverage("control", "positive_control"),), CollectorHealth(), True,
            ),
            (1, 2): OSPermissionRead(
                (), (_coverage("target", "exercise"),), CollectorHealth(), True,
            ),
        }
        self.positions = iter((0, 1, 1, 2))
        self.calls: list[str] = []
        self.request_limits: list[int] = []

    def open(self, *, run_id: str) -> None:
        assert run_id == "run-synthetic"
        self.calls.append("open")

    def start(self) -> None:
        self.calls.append("start")

    def position(self) -> int:
        return next(self.positions)

    def read(self, *, start: int, end: int, limit: int) -> OSPermissionRead:
        self.request_limits.append(limit)
        return self.reads[(start, end)]

    def close(self) -> None:
        self.calls.append("close")


def _windows(
    tmp_path: Path, source: SyntheticOSSource | None, *, verified: bool = True,
) -> tuple[OSPermissionCollector, object, object]:
    # The verifier here only exercises the trust boundary; it is not a native proof.
    verifier = (lambda candidate, context: candidate is source) if verified else None
    collector = OSPermissionCollector(source, verify_source=verifier, max_events=8)
    collector.prepare(CollectionContext(
        "run-synthetic", "H065", "synthetic", tmp_path / "workspace",
        tmp_path / "evidence",
    ))
    collector.start()

    def get_window(label: str) -> ObservationWindow:
        before = collector.checkpoint("before-" + label)
        after = collector.checkpoint("after-" + label)
        return ObservationWindow(
            CollectionCheckpoint("before-" + label, {collector.name: before}),
            CollectionCheckpoint("after-" + label, {collector.name: after}),
            label,
        )

    return collector, get_window("control"), get_window("exercise")


def _assess(baseline: object, exercise: object, **overrides: object):
    arguments = dict(
        positive_control=baseline,
        observation=exercise,
        run_id="run-synthetic",
        control_task_id="control",
        task_id="target",
        permission="microphone",
        process=PROCESS,
    )
    arguments.update(overrides)
    return assess_no_unauthorized_os_access(**arguments)


def test_complete_windows_with_successful_control_allow_a_narrow_zero_access_claim(
    tmp_path: Path,
) -> None:
    source = SyntheticOSSource()
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)

    assert baseline.status is observed.status is CollectorStatus.AVAILABLE
    assert _assess(baseline, observed).verdict is OSAccessVerdict.NO_UNAUTHORIZED_ACCESS
    assert source.request_limits == [8, 8]
    assert baseline.observations[0]["process"] == {
        "pid": 42, "instance_id": PROCESS.instance_id,
    }
    assert baseline.observations[0]["action"] == "granted"
    collector.close()
    collector.close()
    assert source.calls == ["open", "start", "close"]


@pytest.mark.parametrize("action", list(OSPermissionAction))
def test_attempt_granted_or_denied_access_is_detected(
    tmp_path: Path, action: OSPermissionAction,
) -> None:
    source = SyntheticOSSource()
    source.reads[(1, 2)] = replace(
        source.reads[(1, 2)], events=(_event(2, "target", "exercise", action=action),),
    )
    collector, control, exercise = _windows(tmp_path, source)
    assert _assess(collector.collect(control), collector.collect(exercise)).verdict is OSAccessVerdict.UNAUTHORIZED_ACCESS
    collector.close()


def test_access_by_child_process_of_target_task_is_not_ignored(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    child = OSProcessIdentity(43, "synthetic-child-start-token")
    source.reads[(1, 2)] = replace(
        source.reads[(1, 2)],
        events=(_event(2, "target", "exercise", process=child),),
    )
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)

    assert _assess(baseline, observed).verdict is OSAccessVerdict.UNAUTHORIZED_ACCESS
    collector.close()


def test_events_and_nested_process_identity_cannot_change_after_collection(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    source.reads[(1, 2)] = replace(
        source.reads[(1, 2)], events=(_event(2, "target", "exercise"),),
    )
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)

    with pytest.raises(TypeError):
        observed.observations[0]["task_id"] = "another-task"
    with pytest.raises(TypeError):
        observed.observations[0]["process"]["pid"] = 43
    assert _assess(baseline, observed).verdict is OSAccessVerdict.UNAUTHORIZED_ACCESS
    collector.close()


@pytest.mark.parametrize("explicitly_false", (True, False))
def test_missing_process_tree_coverage_cannot_prove_no_access(
    tmp_path: Path, explicitly_false: bool,
) -> None:
    source = SyntheticOSSource()
    coverage = (
        _coverage("target", "exercise", process_tree_complete=False)
        if explicitly_false else OSPermissionCoverage(
            "run-synthetic", "target", "exercise", "microphone", PROCESS, True, True,
        )
    )
    source.reads[(1, 2)] = replace(
        source.reads[(1, 2)],
        coverage=(coverage,),
    )
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)

    assert _assess(baseline, observed).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()


def test_close_retries_after_source_cleanup_failure(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    collector, _, _ = _windows(tmp_path, source)
    close_attempts = 0

    def flaky_close() -> None:
        nonlocal close_attempts
        close_attempts += 1
        if close_attempts == 1:
            raise OSError("temporary close failure")
        source.calls.append("close")

    source.close = flaky_close  # type: ignore[method-assign]
    with pytest.raises(OSError, match="temporary close failure"):
        collector.close()
    collector.close()
    assert close_attempts == 2
    assert source.calls == ["open", "start", "close"]


def test_missing_or_unverified_source_never_claims_zero_access(tmp_path: Path) -> None:
    collector, control, exercise = _windows(tmp_path, None)
    baseline, observed = collector.collect(control), collector.collect(exercise)
    assert baseline.status is observed.status is CollectorStatus.MISSING
    assert _assess(baseline, observed).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()

    source = SyntheticOSSource()
    collector, control, exercise = _windows(tmp_path, source, verified=False)
    assert collector.collect(control).status is CollectorStatus.UNVERIFIED
    assert _assess(collector.collect(control), collector.collect(exercise)).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    assert source.request_limits == []
    collector.close()

    source = SyntheticOSSource()
    source.info = replace(source.info, native_os_events=False)
    collector, control, exercise = _windows(tmp_path, source)
    assert collector.collect(control).status is CollectorStatus.UNVERIFIED
    assert _assess(collector.collect(control), collector.collect(exercise)).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()


@pytest.mark.parametrize("defect", ("lost", "unhealthy", "truncated", "too_many", "unknown_process", "missing_task", "out_of_window"))
def test_incomplete_or_unreliable_windows_are_fail_closed(
    tmp_path: Path, defect: str,
) -> None:
    source = SyntheticOSSource()
    original = source.reads[(1, 2)]
    if defect == "lost":
        original = replace(original, health=CollectorHealth(lost_record_count=1))
    elif defect == "unhealthy":
        original = replace(original, health=CollectorHealth(CollectorHealthState.UNHEALTHY))
    elif defect == "truncated":
        original = replace(original, complete=False)
    elif defect == "too_many":
        original = replace(original, events=tuple(_event(2, "target", "exercise") for _ in range(9)))
    elif defect == "unknown_process":
        original = replace(original, events=(_event(2, "target", "exercise", process=OSProcessIdentity(None, None)),))
    elif defect == "missing_task":
        original = replace(original, events=(replace(_event(2, "target", "exercise"), task_id=None),))
    else:
        original = replace(original, events=(_event(3, "target", "exercise"),))
    source.reads[(1, 2)] = original
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)
    assert observed.status is CollectorStatus.UNVERIFIED
    assert observed.observations == ()
    assert _assess(baseline, observed).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()


@pytest.mark.parametrize("defect", ("no_control", "missing_coverage", "incomplete_coverage", "unknown_process", "different_source", "wrong_permission", "wrong_task", "wrong_run", "same_window"))
def test_baseline_coverage_and_run_binding_are_mandatory(
    tmp_path: Path, defect: str,
) -> None:
    source = SyntheticOSSource()
    if defect == "no_control":
        source.reads[(0, 1)] = replace(source.reads[(0, 1)], events=())
    if defect == "missing_coverage":
        source.reads[(1, 2)] = replace(source.reads[(1, 2)], coverage=())
    if defect == "incomplete_coverage":
        source.reads[(1, 2)] = replace(source.reads[(1, 2)], coverage=(_coverage("target", "exercise", task_finished=False),))
    if defect == "unknown_process":
        source.reads[(1, 2)] = replace(source.reads[(1, 2)], coverage=(_coverage("target", "exercise", process=OSProcessIdentity(42, None)),))
    collector, control, exercise = _windows(tmp_path, source)
    baseline, observed = collector.collect(control), collector.collect(exercise)
    if defect == "different_source":
        observed = replace(observed, diagnostics={**observed.diagnostics, "source_id": "another-source"})
    elif defect == "same_window":
        observed = baseline
    kwargs = {}
    if defect == "wrong_permission":
        kwargs["permission"] = "location"
    elif defect == "wrong_task":
        kwargs["task_id"] = "unknown-task"
    elif defect == "wrong_run":
        kwargs["run_id"] = "another-run"
    assert _assess(baseline, observed, **kwargs).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()


def test_drain_cannot_stand_in_for_a_complete_task_window(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    collector, control, _ = _windows(tmp_path, source)
    baseline = collector.collect(control)
    result = collector.drain(0.5)
    assert result.status is CollectorStatus.UNVERIFIED
    assert _assess(baseline, result).verdict is OSAccessVerdict.INSUFFICIENT_EVIDENCE
    collector.close()


@pytest.mark.parametrize("broken_verifier", ("reject", "raises"))
def test_independent_source_verification_is_required_even_if_source_claims_native(
    tmp_path: Path, broken_verifier: str,
) -> None:
    source = SyntheticOSSource()

    def verify(candidate: SyntheticOSSource, context: CollectionContext) -> bool:
        if broken_verifier == "raises":
            raise RuntimeError("verification unavailable")
        return False

    collector = OSPermissionCollector(source, verify_source=verify)
    collector.prepare(CollectionContext(
        "run-synthetic", "H065", "synthetic", tmp_path / "workspace",
        tmp_path / "evidence",
    ))
    collector.start()
    start = collector.checkpoint("start")
    stop = collector.checkpoint("stop")
    observed = collector.collect(ObservationWindow(
        CollectionCheckpoint("start", {collector.name: start}),
        CollectionCheckpoint("stop", {collector.name: stop}),
        "unverified",
    ))
    assert observed.status is CollectorStatus.UNVERIFIED
    assert observed.observations == ()
    assert source.request_limits == []
    collector.close()


def test_source_exception_is_reported_without_raw_error_payload(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    collector, control, _ = _windows(tmp_path, source)

    def broken(*, start: int, end: int, limit: int) -> OSPermissionRead:
        raise RuntimeError("PRIVATE_TOKEN_SHOULD_NOT_APPEAR")

    source.read = broken  # type: ignore[method-assign]
    result = collector.collect(control)
    assert result.status is CollectorStatus.ERROR
    assert "PRIVATE_TOKEN_SHOULD_NOT_APPEAR" not in repr(result)
    collector.close()


def test_unissued_window_and_invalid_cursor_are_rejected(tmp_path: Path) -> None:
    source = SyntheticOSSource()
    collector, control, exercise = _windows(tmp_path, source)
    alien = CollectionCheckpoint("alien", {collector.name: replace(exercise.end.cursors[collector.name], value="999")})
    with pytest.raises(ValueError, match="issued"):
        collector.collect(ObservationWindow(control.start, alien, "alien"))
    collector.close()
    with pytest.raises(RuntimeError, match="not running"):
        collector.collect(control)
