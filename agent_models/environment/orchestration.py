"""Bounded cooperative scheduling for evaluator-owned activities."""

from __future__ import annotations

import math
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class ScenarioTimeout(TimeoutError):
    """A deadline expired; pending workers may not be declared stopped."""


def _timeout(value: float, name: str, *, allow_zero: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero) or value > threading.TIMEOUT_MAX:
        raise ValueError(f"{name} must be finite and within supported time bounds")
    return float(value)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    deadline: float
    stop: threading.Event

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a nonempty string")
        if type(self.deadline) not in (int, float) or not math.isfinite(self.deadline):
            raise ValueError("deadline must be finite")

    def checkpoint(self) -> None:
        if self.stop.is_set() or time.monotonic() >= self.deadline:
            raise ScenarioTimeout("test-side activity cancelled or deadline exceeded")

    def wait(self, event: threading.Event) -> None:
        """Synchronize on a real event with bounded cancellation latency."""
        while True:
            self.checkpoint()
            if event.wait(min(0.02, max(0, self.deadline - time.monotonic()))):
                self.checkpoint()
                return

    def delay(self, seconds: float) -> None:
        """Inject intentional test-side delay, not arbitrary process synchronization."""
        seconds = _timeout(seconds, "delay", allow_zero=True)
        self.checkpoint()
        remaining = self.deadline - time.monotonic()
        if self.stop.wait(min(seconds, remaining)) or seconds >= remaining:
            raise ScenarioTimeout("delay cancelled or deadline exceeded")
        self.checkpoint()


class ScenarioRunner:
    """Run bounded activities; cancellation never claims to stop the real Agent."""

    def __init__(self, *, max_workers: int = 16, event_sink=None) -> None:
        if type(max_workers) is not int or max_workers < 1:
            raise ValueError("max_workers must be a positive integer")
        self.max_workers = max_workers
        self.event_sink = event_sink
        self._lock = threading.RLock()
        self._operation_lock = threading.RLock()
        self._parallel_active = False
        self._threads: list[threading.Thread] = []
        self._stops: list[threading.Event] = []
        self._closed = False

    def _record(self, kind: str, data: dict, run_id: str) -> None:
        if self.event_sink:
            self.event_sink("scenario_runner", kind, data, correlation_id=run_id)

    def parallel(self, actions: Mapping[str, Callable[[RunContext], Any]], *,
                 timeout: float = 30, run_id: str | None = None) -> dict[str, Any]:
        """Reserve the coordinator until final evidence and results are finalized."""
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("runner preceding operation has not stopped")
        try:
            with self._lock:
                if self._parallel_active:
                    raise RuntimeError("recursive parallel operation is not supported")
                self._parallel_active = True
            try:
                return self._parallel(actions, timeout=timeout, run_id=run_id)
            finally:
                with self._lock:
                    self._parallel_active = False
        finally:
            self._operation_lock.release()

    def _parallel(self, actions: Mapping[str, Callable[[RunContext], Any]], *,
                  timeout: float, run_id: str | None) -> dict[str, Any]:
        actions = dict(actions)
        if not actions or len(actions) > self.max_workers:
            raise ValueError("activity count must be between one and max_workers")
        if any(not isinstance(name, str) or not name or not callable(action)
               for name, action in actions.items()):
            raise ValueError("activities require nonempty names and callables")
        timeout = _timeout(timeout, "timeout")
        if run_id is not None and (not isinstance(run_id, str) or not run_id):
            raise ValueError("run_id must be a nonempty string")
        with self._lock:
            if self._closed or any(t.is_alive() for t in self._threads):
                raise RuntimeError("runner closed or preceding activities have not stopped")
            stop, start = threading.Event(), threading.Event()
            context = RunContext(run_id or uuid.uuid4().hex, time.monotonic() + timeout, stop)
            condition = threading.Condition()
            results: dict[str, Any] = {}
            failures: list[BaseException] = []
            finished: set[str] = set()

            def worker(name, action):
                start.wait()
                try:
                    context.checkpoint()
                    self._record("activity_started", {"name": name}, context.run_id)
                    result = action(context)
                    context.checkpoint()
                    self._record("activity_completed", {"name": name}, context.run_id)
                    with condition:
                        results[name] = result
                except BaseException as error:
                    with condition:
                        failures.append(error)
                        stop.set()
                finally:
                    with condition:
                        finished.add(name)
                        condition.notify_all()

            threads = [threading.Thread(target=worker, args=(name, action),
                                        name=f"ats-{name}", daemon=True)
                       for name, action in actions.items()]
            self._threads = []
            self._stops = [stop]
            try:
                self._record("run_started", {"activities": list(actions)}, context.run_id)
                for thread in threads:
                    thread.start()
                    self._threads.append(thread)
            except BaseException as error:
                stop.set()
                start.set()  # Wake every already-started worker even on partial startup.
                for thread in self._threads:
                    thread.join(timeout=0.1)
                startup_errors = [error]
                if any(thread.is_alive() for thread in self._threads):
                    startup_errors.append(ScenarioTimeout("startup workers not confirmed stopped"))
                try:
                    self._record("run_failed", {"error_types": [type(e).__name__ for e in startup_errors]}, context.run_id)
                except BaseException as recording_error:
                    startup_errors.append(recording_error)
                raise BaseExceptionGroup("test-side activity startup failed", startup_errors)
            finally:
                start.set()
        with condition:
            while len(finished) < len(actions):
                remaining = context.deadline - time.monotonic()
                if remaining <= 0:
                    stop.set()
                    break
                condition.wait(min(remaining, 0.05))
        # Cooperative workers exit promptly; uncooperative work is surfaced, never hidden.
        for thread in threads:
            thread.join(timeout=max(0, min(0.05, context.deadline - time.monotonic())))
        pending = [name for name, thread in zip(actions, threads) if thread.is_alive()]
        if pending:
            self._record("run_incomplete", {"pending": pending}, context.run_id)
            raise ScenarioTimeout(f"activities not confirmed stopped: {', '.join(pending)}")
        if failures:
            self._record("run_failed", {"error_types": [type(e).__name__ for e in failures]}, context.run_id)
            raise BaseExceptionGroup("test-side activities failed", failures)
        if len(results) != len(actions) or time.monotonic() >= context.deadline or stop.is_set():
            self._record("run_incomplete", {"reason": "deadline exceeded or cancellation requested"}, context.run_id)
            raise ScenarioTimeout("activities exceeded deadline or were cancelled")
        self._record("run_completed", {"activities": list(results)}, context.run_id)
        return {name: results[name] for name in actions}

    def repeat(self, count: int, action: Callable[[RunContext], Any], *,
               prepare: Callable[[RunContext], None], restore: Callable[[RunContext], None],
               timeout: float = 30) -> list[Any]:
        """Use fresh IDs; restore in the caller only after workers have stopped.

        This does not create Agent sessions. The action must create a fresh model
        when session independence is required. Restore callbacks own a bounded
        cleanup timeout; an uncooperative live worker prevents unsafe restoration.
        """
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("runner preceding operation has not stopped")
        try:
            return self._repeat(count, action, prepare=prepare, restore=restore, timeout=timeout)
        finally:
            self._operation_lock.release()

    def _repeat(self, count: int, action: Callable[[RunContext], Any], *,
                prepare: Callable[[RunContext], None], restore: Callable[[RunContext], None],
                timeout: float) -> list[Any]:
        if type(count) is not int or count < 1:
            raise ValueError("repeat count must be a positive integer")
        _timeout(timeout, "timeout")
        if not all(callable(callback) for callback in (action, prepare, restore)):
            raise ValueError("repeat callbacks must be callable")
        outcomes = []
        for index in range(count):
            contexts: list[RunContext] = []
            def attempt(context):
                contexts.append(context)
                prepare(context)
                context.checkpoint()
                return action(context)
            errors: list[BaseException] = []
            result = None
            try:
                result = self.parallel({f"repeat-{index + 1}": attempt}, timeout=timeout)
            except BaseException as error:
                errors.append(error)
            finally:
                if contexts:
                    if self.health()["active_workers"]:
                        errors.append(ScenarioTimeout("restoration deferred: activities remain alive"))
                    else:
                        try:
                            restore(contexts[0])
                        except BaseException as error:
                            errors.append(error)
            if errors:
                raise BaseExceptionGroup("attempt or restoration failed", errors)
            outcomes.append(result[f"repeat-{index + 1}"])
        return outcomes

    def health(self) -> dict[str, Any]:
        with self._lock:
            active = sum(t.is_alive() for t in self._threads)
            return {"healthy": not self._closed and active == 0 and not self._parallel_active,
                    "active_workers": active, "coordinator_active": self._parallel_active,
                    "closed": self._closed}

    def close(self, *, timeout: float = 1) -> None:
        timeout = _timeout(timeout, "close timeout")
        with self._lock:
            self._closed = True
            for stop in self._stops:
                stop.set()
            threads = list(self._threads)
        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0, deadline - time.monotonic()))
        if any(thread.is_alive() for thread in threads):
            raise ScenarioTimeout("cannot restore environment while activities remain alive")
        acquired = self._operation_lock.acquire(timeout=max(0, deadline - time.monotonic()))
        if not acquired:
            raise ScenarioTimeout("scenario coordinator or restoration has not stopped")
        try:
            if self._parallel_active:
                raise ScenarioTimeout("cannot close from an active scenario coordinator")
        finally:
            self._operation_lock.release()

    def __enter__(self) -> ScenarioRunner:
        return self

    def __exit__(self, *_args) -> None:
        self.close()
