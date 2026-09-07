"""Verify event-based parallel work and independent repeat restoration."""

import threading
import time

import pytest

from agent_models.environment.orchestration import RunContext, ScenarioRunner, ScenarioTimeout


def test_parallel_uses_real_event_synchronization():
    event = threading.Event()
    with ScenarioRunner() as runner:
        result = runner.parallel({"wait": lambda ctx: ctx.wait(event),
                                  "signal": lambda ctx: event.set()}, timeout=1)
        assert list(result) == ["wait", "signal"]
        assert runner.health()["active_workers"] == 0


def test_repeat_restores_each_attempt_and_has_distinct_ids():
    state, ids, restored = [], [], []
    with ScenarioRunner() as runner:
        def action(ctx):
            assert state == ["baseline"]
            ids.append(ctx.run_id)
            state.append("effect")
            return len(state)
        values = runner.repeat(3, action, prepare=lambda ctx: state.append("baseline"),
                               restore=lambda ctx: (state.clear(), restored.append(ctx.run_id)))
    assert values == [2, 2, 2] and len(set(ids)) == 3 and restored == ids and not state


def test_action_and_restore_errors_are_both_preserved():
    def action(ctx):
        raise ValueError("action failed")
    def restore(ctx):
        raise OSError("restore failed")
    with ScenarioRunner() as runner:
        with pytest.raises(ExceptionGroup) as exc:
            runner.repeat(1, action, prepare=lambda ctx: None, restore=restore)
    assert isinstance(exc.value.exceptions[0].exceptions[0], ValueError)
    assert isinstance(exc.value.exceptions[1], OSError)


def test_repeat_never_restores_under_uncooperative_worker():
    release, restored = threading.Event(), []
    runner = ScenarioRunner()
    try:
        with pytest.raises(ExceptionGroup):
            runner.repeat(1, lambda ctx: release.wait(), prepare=lambda ctx: None,
                          restore=lambda ctx: restored.append(True), timeout=0.03)
        assert not restored
    finally:
        release.set()
        runner.close()


def test_uncooperative_activity_cannot_be_reported_as_stopped():
    release = threading.Event()
    runner = ScenarioRunner()
    try:
        with pytest.raises(ScenarioTimeout, match="not confirmed stopped"):
            runner.parallel({"blocked": lambda ctx: release.wait()}, timeout=0.03)
        assert runner.health()["active_workers"] == 1
        with pytest.raises(RuntimeError, match="not stopped"):
            runner.parallel({"next": lambda ctx: None})
    finally:
        release.set()
        runner.close()


def test_failure_signals_other_cooperative_workers():
    never = threading.Event()
    def fail(ctx):
        raise ValueError("expected")
    with ScenarioRunner() as runner:
        with pytest.raises(ExceptionGroup):
            runner.parallel({"waiter": lambda ctx: ctx.wait(never), "failure": fail}, timeout=1)
        assert runner.health()["active_workers"] == 0


def test_partial_thread_start_failure_wakes_and_joins_started_workers(monkeypatch):
    runner = ScenarioRunner()
    original_start = threading.Thread.start
    started, events = [], []
    runner.event_sink = lambda source, kind, data, **kwargs: events.append(kind)
    def start(thread):
        if started:
            raise RuntimeError("synthetic thread creation failure")
        original_start(thread)
        started.append(thread)
    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", start)
        with pytest.raises(ExceptionGroup, match="startup failed"):
            runner.parallel({"first": lambda ctx: None, "second": lambda ctx: None})
    assert started and not any(thread.is_alive() for thread in started)
    assert runner.health()["active_workers"] == 0
    assert "run_failed" in events
    assert runner.parallel({"next": lambda ctx: "ok"}) == {"next": "ok"}
    runner.close()


def test_parallel_reserves_coordinator_until_final_evidence_is_written():
    finalizing, release = threading.Event(), threading.Event()
    outcomes, errors = [], []
    def sink(source, kind, data, **kwargs):
        if kind == "run_completed":
            finalizing.set()
            assert release.wait(2)
    runner = ScenarioRunner(event_sink=sink)
    def run():
        try:
            outcomes.append(runner.parallel({"first": lambda ctx: 1}))
        except BaseException as error:
            errors.append(error)
    coordinator = threading.Thread(target=run)
    coordinator.start()
    try:
        assert finalizing.wait(2)
        assert runner.health()["active_workers"] == 0
        assert runner.health()["coordinator_active"]
        with pytest.raises(RuntimeError, match="not stopped"):
            runner.parallel({"second": lambda ctx: 2})
        with pytest.raises(ScenarioTimeout, match="coordinator"):
            runner.close(timeout=0.02)
    finally:
        release.set()
        coordinator.join(2)
        runner.close()
    assert outcomes == [{"first": 1}] and not errors


def test_repeat_reserves_runner_during_caller_restoration():
    restoring, release = threading.Event(), threading.Event()
    failures = []
    runner = ScenarioRunner()
    def restore(ctx):
        restoring.set()
        assert release.wait(2)
    def repeat():
        try:
            runner.repeat(1, lambda ctx: None, prepare=lambda ctx: None, restore=restore)
        except BaseException as error:
            failures.append(error)
    coordinator = threading.Thread(target=repeat)
    coordinator.start()
    try:
        assert restoring.wait(2)
        assert runner.health()["active_workers"] == 0
        with pytest.raises(RuntimeError, match="not stopped"):
            runner.parallel({"other": lambda ctx: None})
        with pytest.raises(ScenarioTimeout, match="restoration"):
            runner.close(timeout=0.02)
    finally:
        release.set()
        coordinator.join(2)
        runner.close()
    assert not failures


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf"), threading.TIMEOUT_MAX * 2, "1"])
def test_invalid_deadlines_are_rejected_before_work_starts(timeout):
    runner = ScenarioRunner()
    called = []
    with pytest.raises(ValueError):
        runner.parallel({"action": lambda ctx: called.append(True)}, timeout=timeout)
    with pytest.raises(ValueError):
        runner.repeat(1, lambda ctx: None, prepare=lambda ctx: None, restore=lambda ctx: None, timeout=timeout)
    with pytest.raises(ValueError):
        runner.close(timeout=timeout)
    assert not called
    runner.close()


@pytest.mark.parametrize("run_id", ["", 1, False])
def test_invalid_run_ids_are_not_silently_replaced(run_id):
    with ScenarioRunner() as runner:
        with pytest.raises(ValueError):
            runner.parallel({"action": lambda ctx: None}, run_id=run_id)


def test_direct_context_rejects_nonfinite_deadline_and_invalid_delay():
    with pytest.raises(ValueError):
        RunContext("run", float("nan"), threading.Event())
    context = RunContext("run", time.monotonic() + 1, threading.Event())
    for delay in [True, "1", float("inf"), threading.TIMEOUT_MAX * 2]:
        with pytest.raises(ValueError):
            context.delay(delay)
