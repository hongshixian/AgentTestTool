"""Lifecycle orchestration for run-scoped evidence collectors."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from evidence_collectors.base import (
    CollectionCheckpoint,
    CollectionContext,
    CollectorLaunchConfig,
    CollectorResult,
    EvidenceCollector,
    EvidenceCursor,
    ObservationWindow,
    utc_now,
)


class ManagerState(str, Enum):
    NEW = "new"
    PREPARED = "prepared"
    STARTED = "started"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class CollectorFailure:
    collector_name: str
    stage: str
    error: BaseException


class EvidenceCollectionError(RuntimeError):
    """One or more collectors failed during the same lifecycle stage."""

    def __init__(self, stage: str, failures: Iterable[CollectorFailure]) -> None:
        self.stage = stage
        self.failures = tuple(failures)
        if not self.failures:
            raise ValueError("evidence collection error requires at least one failure")
        details = "; ".join(
            f"{failure.collector_name}: {type(failure.error).__name__}: {failure.error}"
            for failure in self.failures
        )
        super().__init__(f"Evidence collector {stage} failed: {details}")


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    results: Mapping[str, CollectorResult]

    def __post_init__(self) -> None:
        results = dict(self.results)
        for name, result in results.items():
            if result.collector_name != name:
                raise ValueError("collector results must match their mapping names")
        object.__setattr__(self, "results", MappingProxyType(results))


class EvidenceCollectorManager:
    """Coordinate collectors while preserving explicit errors and cleanup order."""

    def __init__(self, collectors: Iterable[EvidenceCollector]) -> None:
        ordered = tuple(collectors)
        names = tuple(collector.name for collector in ordered)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("collector names must be nonempty strings")
        if len(names) != len(set(names)):
            raise ValueError("collector names must be unique")
        self._collectors = ordered
        self._state = ManagerState.NEW
        self._prepared: list[EvidenceCollector] = []
        self._started: list[EvidenceCollector] = []
        self._environment_overrides: dict[str, str] = {}

    @property
    def state(self) -> ManagerState:
        return self._state

    @property
    def environment_overrides(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self._environment_overrides))

    def prepare(self, context: CollectionContext) -> CollectorLaunchConfig:
        self._require_state(ManagerState.NEW, "prepare")
        overrides: dict[str, str] = {}
        owners: dict[str, str] = {}
        try:
            for collector in self._collectors:
                self._prepared.append(collector)
                config = collector.prepare(context)
                if not isinstance(config, CollectorLaunchConfig):
                    raise TypeError("prepare() must return CollectorLaunchConfig")
                for key, value in config.environment_overrides.items():
                    if key in overrides and overrides[key] != value:
                        raise ValueError(
                            f"environment override {key!r} conflicts with collector "
                            f"{owners[key]!r}"
                        )
                    overrides[key] = value
                    owners.setdefault(key, collector.name)
        except Exception as exc:
            failed_name = collector.name
            cleanup_failures = self._close_collectors(self._prepared)
            self._state = (
                ManagerState.PREPARED if cleanup_failures else ManagerState.CLOSED
            )
            failures = [CollectorFailure(failed_name, "prepare", exc)]
            failures.extend(cleanup_failures)
            raise EvidenceCollectionError("prepare", failures) from exc
        self._environment_overrides = overrides
        self._state = ManagerState.PREPARED
        return CollectorLaunchConfig(overrides)

    def start(self) -> None:
        self._require_state(ManagerState.PREPARED, "start")
        try:
            for collector in self._collectors:
                collector.start()
                self._started.append(collector)
        except Exception as exc:
            failed_name = collector.name
            cleanup_failures = self._close_collectors(self._prepared)
            self._state = (
                ManagerState.PREPARED if cleanup_failures else ManagerState.CLOSED
            )
            failures = [CollectorFailure(failed_name, "start", exc)]
            failures.extend(cleanup_failures)
            raise EvidenceCollectionError("start", failures) from exc
        self._state = ManagerState.STARTED

    def checkpoint(self, label: str) -> CollectionCheckpoint:
        self._require_state(ManagerState.STARTED, "checkpoint")
        cursors: dict[str, EvidenceCursor] = {}
        failures: list[CollectorFailure] = []
        for collector in self._collectors:
            try:
                cursor = collector.checkpoint(label)
                if not isinstance(cursor, EvidenceCursor):
                    raise TypeError("checkpoint() must return EvidenceCursor")
                if cursor.collector_name != collector.name:
                    raise ValueError("checkpoint cursor belongs to another collector")
                cursors[collector.name] = cursor
            except Exception as exc:
                failures.append(CollectorFailure(collector.name, "checkpoint", exc))
        if failures:
            raise EvidenceCollectionError("checkpoint", failures)
        return CollectionCheckpoint(label, cursors, utc_now())

    def collect(self, window: ObservationWindow) -> CollectionBatch:
        self._require_state(ManagerState.STARTED, "collect")
        return self._gather("collect", lambda collector: collector.collect(window))

    def drain(self, timeout_seconds: float) -> CollectionBatch:
        self._require_state(ManagerState.STARTED, "drain")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        return self._gather(
            "drain", lambda collector: collector.drain(float(timeout_seconds))
        )

    def close(self) -> None:
        if self._state is ManagerState.CLOSED:
            return
        failures = self._close_collectors(self._prepared)
        if failures:
            raise EvidenceCollectionError("close", failures)
        self._state = ManagerState.CLOSED

    @contextmanager
    def running(
        self, context: CollectionContext
    ) -> Iterator["EvidenceCollectorManager"]:
        """Prepare, start, and always close all collectors around one Agent run."""

        try:
            self.prepare(context)
            self.start()
            yield self
        except BaseException as primary_error:
            try:
                self.close()
            except BaseException as close_error:
                raise BaseExceptionGroup(
                    "Evidence collection and cleanup both failed",
                    [primary_error, close_error],
                )
            raise
        else:
            self.close()

    def _gather(
        self,
        stage: str,
        operation: Callable[[EvidenceCollector], CollectorResult],
    ) -> CollectionBatch:
        results: dict[str, CollectorResult] = {}
        failures: list[CollectorFailure] = []
        for collector in self._collectors:
            try:
                result = operation(collector)
                if not isinstance(result, CollectorResult):
                    raise TypeError(f"{stage}() must return CollectorResult")
                if result.collector_name != collector.name:
                    raise ValueError(f"{stage} result belongs to another collector")
                results[collector.name] = result
            except Exception as exc:
                failures.append(CollectorFailure(collector.name, stage, exc))
        if failures:
            raise EvidenceCollectionError(stage, failures)
        return CollectionBatch(results)

    def _close_collectors(
        self, collectors: Iterable[EvidenceCollector]
    ) -> list[CollectorFailure]:
        failures: list[CollectorFailure] = []
        for collector in reversed(tuple(collectors)):
            try:
                collector.close()
            except Exception as exc:
                failures.append(CollectorFailure(collector.name, "close", exc))
        return failures

    def _require_state(self, expected: ManagerState, operation: str) -> None:
        if self._state is not expected:
            raise RuntimeError(
                f"cannot {operation} evidence collectors while manager is "
                f"{self._state.value}; expected {expected.value}"
            )


__all__ = [
    "CollectionBatch",
    "CollectorFailure",
    "EvidenceCollectionError",
    "EvidenceCollectorManager",
    "ManagerState",
]
