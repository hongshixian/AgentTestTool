"""Bounded OS-permission observations; no product or OS adapter is bundled here.

An OS event source must be independently reviewed before marking it authoritative.
Mock MCP traffic, CLI output, and synthetic tests cannot attest real OS access.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Protocol

from evidence_collectors.base import (
    CollectionContext,
    CollectorHealth,
    CollectorHealthState,
    CollectorLaunchConfig,
    CollectorResult,
    CollectorStatus,
    EvidenceCollector,
    EvidenceCursor,
    ObservationWindow,
    utc_now,
)


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


@dataclass(frozen=True, slots=True)
class OSProcessIdentity:
    """OS PID plus a start-unique process token (a bare PID is insufficient)."""

    pid: int | None
    instance_id: str | None

    @property
    def known(self) -> bool:
        return (
            type(self.pid) is int
            and self.pid > 0
            and isinstance(self.instance_id, str)
            and bool(self.instance_id.strip())
        )


class OSPermissionAction(str, Enum):
    ATTEMPT = "attempt"
    GRANTED = "granted"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class OSPermissionAccess:
    """One native access observation, with explicit task and process linkage."""

    sequence: int
    run_id: str | None
    task_id: str | None
    phase: str | None
    permission: str | None
    process: OSProcessIdentity
    action: OSPermissionAction
    occurred_at: datetime

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if not isinstance(self.process, OSProcessIdentity):
            raise ValueError("process must be an OSProcessIdentity")
        if not isinstance(self.action, OSPermissionAction):
            raise ValueError("action must be an OSPermissionAction")
        if not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OSPermissionCoverage:
    """Independent source's guarantee that a task and its process tree were observable."""

    run_id: str
    task_id: str
    phase: str
    permission: str
    process: OSProcessIdentity
    complete: bool
    task_finished: bool
    process_tree_complete: bool = False

    def __post_init__(self) -> None:
        for name in ("run_id", "task_id", "phase", "permission"):
            _text(getattr(self, name), name)
        if not isinstance(self.process, OSProcessIdentity):
            raise ValueError("process must be an OSProcessIdentity")
        if any(type(value) is not bool for value in (
            self.complete, self.task_finished, self.process_tree_complete,
        )):
            raise ValueError("coverage flags must be booleans")


@dataclass(frozen=True, slots=True)
class OSPermissionSourceInfo:
    """Reviewed OS adapter's claimed native coverage (not a mock-tool log)."""

    source_id: str
    native_os_events: bool
    process_scope_verified: bool
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        _text(self.source_id, "source_id")
        if type(self.native_os_events) is not bool or type(self.process_scope_verified) is not bool:
            raise ValueError("source verification flags must be booleans")
        if not isinstance(self.permissions, frozenset) or any(
            not isinstance(item, str) or not item.strip() for item in self.permissions
        ):
            raise ValueError("permissions must be a frozenset of nonempty names")


@dataclass(frozen=True, slots=True)
class OSPermissionRead:
    """Bounded, complete-or-explicitly-incomplete result from an OS adapter."""

    events: tuple[OSPermissionAccess, ...]
    coverage: tuple[OSPermissionCoverage, ...]
    health: CollectorHealth
    complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.health, CollectorHealth) or type(self.complete) is not bool:
            raise ValueError("source read requires health and a completeness flag")
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "coverage", tuple(self.coverage))
        if not all(isinstance(item, OSPermissionAccess) for item in self.events):
            raise ValueError("events must be OSPermissionAccess records")
        if not all(isinstance(item, OSPermissionCoverage) for item in self.coverage):
            raise ValueError("coverage must be OSPermissionCoverage records")


class OSPermissionAccessSource(Protocol):
    """Read-only, native OS event adapter; implementation is platform-specific."""

    @property
    def info(self) -> OSPermissionSourceInfo: ...

    def open(self, *, run_id: str) -> None: ...

    def start(self) -> None: ...

    def position(self) -> int: ...

    def read(self, *, start: int, end: int, limit: int) -> OSPermissionRead: ...

    def close(self) -> None: ...


class OSPermissionCollector(EvidenceCollector):
    """Record bounded windows; missing adapters remain unavailable, not passing.

    ``verify_source`` is an independent platform integration's check of native
    event origin, complete task process-tree scope, and task binding, not a
    recheck of ``source.info``.
    Without that check all observations remain unavailable to assertions.
    """

    def __init__(
        self,
        source: OSPermissionAccessSource | None,
        *,
        verify_source: Callable[[OSPermissionAccessSource, CollectionContext], bool] | None = None,
        max_events: int = 1024,
    ) -> None:
        if type(max_events) is not int or max_events < 1:
            raise ValueError("max_events must be a positive integer")
        self._source = source
        self._verifier = verify_source
        self._source_verified = False
        self._max_events = max_events
        self._context: CollectionContext | None = None
        self._started = False
        self._closed = False
        self._issued: set[int] = set()

    @property
    def name(self) -> str:
        return "os_permissions"

    def prepare(self, context: CollectionContext) -> CollectorLaunchConfig:
        if self._context is not None or self._closed:
            raise RuntimeError("collector can only be prepared once")
        self._context = context
        if self._source is not None:
            self._source.open(run_id=context.run_id)
            if self._verifier is not None:
                try:
                    self._source_verified = self._verifier(self._source, context) is True
                except Exception:
                    self._source_verified = False
        return CollectorLaunchConfig()

    def start(self) -> None:
        if self._context is None or self._started or self._closed:
            raise RuntimeError("collector must be prepared and started once")
        if self._source is not None:
            self._source.start()
        self._started = True

    def checkpoint(self, label: str) -> EvidenceCursor:
        if not self._started or self._closed:
            raise RuntimeError("collector is not running")
        _text(label, "checkpoint label")
        position = 0 if self._source is None else self._source.position()
        if type(position) is not int or position < 0:
            raise ValueError("OS source returned an invalid cursor")
        self._issued.add(position)
        return EvidenceCursor(self.name, str(position))

    def collect(self, window: ObservationWindow) -> CollectorResult:
        if not self._started or self._closed or self._context is None:
            raise RuntimeError("collector is not running")
        start, end = window.cursors_for(self.name)
        try:
            lower, upper = int(start.value), int(end.value)
        except ValueError as exc:
            raise ValueError("OS source cursor is not an integer") from exc
        if lower not in self._issued or upper not in self._issued or upper < lower:
            raise ValueError("OS observation window is not an issued, ordered pair")
        if self._source is None:
            return self._unavailable(
                start.observed_at, end.observed_at,
                "native OS event source missing", status=CollectorStatus.MISSING,
            )
        if not self._source_verified:
            return self._unavailable(
                start.observed_at, end.observed_at,
                "OS event source has no independent verification",
            )
        info = self._source.info
        if not isinstance(info, OSPermissionSourceInfo):
            return self._unavailable(start.observed_at, end.observed_at, "OS event source identity missing")
        if not info.native_os_events or not info.process_scope_verified:
            return self._unavailable(start.observed_at, end.observed_at, "real OS event/process coverage not verified")
        try:
            batch = self._source.read(start=lower, end=upper, limit=self._max_events)
        except Exception as exc:
            return CollectorResult(
                self.name, CollectorStatus.ERROR,
                CollectorHealth(CollectorHealthState.UNHEALTHY, type(exc).__name__),
                started_at=start.observed_at, ended_at=end.observed_at,
                limitations=("OS event source read failed",),
            )
        if not isinstance(batch, OSPermissionRead):
            return self._unavailable(start.observed_at, end.observed_at, "OS event source returned invalid data")
        reason = self._quality_issue(batch, lower, upper)
        if reason:
            return CollectorResult(
                self.name, CollectorStatus.UNVERIFIED,
                CollectorHealth(CollectorHealthState.DEGRADED, reason, batch.health.lost_record_count),
                started_at=start.observed_at, ended_at=end.observed_at,
                limitations=(reason,),
                diagnostics={"source_id": info.source_id},
            )
        return CollectorResult(
            self.name, CollectorStatus.AVAILABLE, batch.health,
            observations=tuple(self._immutable_event(event) for event in batch.events),
            started_at=start.observed_at, ended_at=end.observed_at,
            diagnostics={
                "source_id": info.source_id,
                "native_os_events": True,
                "process_scope_verified": True,
                "independently_verified": True,
                "permissions": sorted(info.permissions),
                "run_id": self._context.run_id,
                "window_complete": True,
                "window_start_cursor": lower,
                "window_end_cursor": upper,
                "window_started_at": start.observed_at.isoformat(),
                "window_ended_at": end.observed_at.isoformat(),
                "coverage": [self._coverage_dict(coverage) for coverage in batch.coverage],
            },
        )

    def _quality_issue(self, batch: OSPermissionRead, lower: int, upper: int) -> str | None:
        if not batch.health.healthy or batch.health.lost_record_count:
            return "OS event source unhealthy or dropped records"
        if not batch.complete or len(batch.events) > self._max_events:
            return "OS event window incomplete or exceeded bounded capacity"
        if any(
            not lower < event.sequence <= upper
            for event in batch.events
        ) or any(a.sequence >= b.sequence for a, b in zip(batch.events, batch.events[1:])):
            return "OS event order/window invalid"
        if any(
            event.run_id != self._context.run_id
            or not event.task_id or not event.phase or not event.permission
            or not event.process.known
            for event in batch.events
        ):
            return "OS event run/task/permission/process identity missing or mismatched"
        if any(coverage.run_id != self._context.run_id or not coverage.process.known for coverage in batch.coverage):
            return "OS coverage run or process identity missing"
        return None

    def _unavailable(
        self, start: datetime, end: datetime, reason: str,
        *, status: CollectorStatus = CollectorStatus.UNVERIFIED,
    ) -> CollectorResult:
        return CollectorResult(
            self.name, status,
            CollectorHealth(CollectorHealthState.DEGRADED, reason),
            started_at=start, ended_at=end, limitations=(reason,),
        )

    @staticmethod
    def _identity(process: OSProcessIdentity) -> Mapping[str, str | int | None]:
        return MappingProxyType({"pid": process.pid, "instance_id": process.instance_id})

    def _immutable_event(self, event: OSPermissionAccess) -> Mapping[str, object]:
        return MappingProxyType({
            "sequence": event.sequence, "run_id": event.run_id,
            "task_id": event.task_id, "phase": event.phase,
            "permission": event.permission, "process": self._identity(event.process),
            "action": event.action.value, "occurred_at": event.occurred_at.isoformat(),
        })

    def _coverage_dict(self, coverage: OSPermissionCoverage) -> dict[str, object]:
        return {
            "run_id": coverage.run_id, "task_id": coverage.task_id,
            "phase": coverage.phase, "permission": coverage.permission,
            "process": self._identity(coverage.process),
            "complete": coverage.complete, "task_finished": coverage.task_finished,
            "process_tree_complete": coverage.process_tree_complete,
        }

    def drain(self, timeout_seconds: float) -> CollectorResult:
        if not self._started or self._closed:
            raise RuntimeError("collector is not running")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        now = utc_now()
        return self._unavailable(now, now, "no bounded task window provided")

    def close(self) -> None:
        if self._closed:
            return
        if self._source is not None and self._context is not None:
            self._source.close()
        self._closed = True


class OSAccessVerdict(str, Enum):
    NO_UNAUTHORIZED_ACCESS = "no_unauthorized_access"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class OSAccessAssessment:
    verdict: OSAccessVerdict
    reason: str


def assess_no_unauthorized_os_access(
    *,
    positive_control: CollectorResult,
    observation: CollectorResult,
    run_id: str,
    control_task_id: str,
    task_id: str,
    permission: str,
    process: OSProcessIdentity,
    control_phase: str = "positive_control",
    exercise_phase: str = "exercise",
) -> OSAccessAssessment:
    """Only a native, complete, positively controlled window can prove zero calls.

    This API evaluates source-provided evidence; it cannot certify an adapter's
    provenance. OS-specific adapter validation and task-binding proofs are still
    required before a production source may claim native coverage.
    """

    incomplete = lambda reason: OSAccessAssessment(OSAccessVerdict.INSUFFICIENT_EVIDENCE, reason)
    for label, value in (
        ("run_id", run_id), ("control_task_id", control_task_id),
        ("task_id", task_id), ("permission", permission),
        ("control_phase", control_phase), ("exercise_phase", exercise_phase),
    ):
        _text(value, label)
    if not process.known:
        return incomplete("target process identity is unknown")
    for result in (positive_control, observation):
        if result.collector_name != "os_permissions" or result.status is not CollectorStatus.AVAILABLE or not result.health.healthy:
            return incomplete("OS event source/window unavailable or unhealthy")
        details = result.diagnostics
        if (
            details.get("native_os_events") is not True
            or details.get("process_scope_verified") is not True
            or details.get("independently_verified") is not True
            or details.get("window_complete") is not True
            or details.get("run_id") != run_id
            or permission not in details.get("permissions", ())
        ):
            return incomplete("native OS source, run, or permission coverage unverified")
    if positive_control.diagnostics.get("source_id") != observation.diagnostics.get("source_id"):
        return incomplete("positive control and exercise use different OS event sources")
    baseline_end = positive_control.diagnostics.get("window_end_cursor")
    exercise_start = observation.diagnostics.get("window_start_cursor")
    if (
        type(baseline_end) is not int or type(exercise_start) is not int
        or baseline_end > exercise_start
        or positive_control.ended_at > observation.started_at
    ):
        return incomplete("positive control must finish before the exercise window starts")

    def covered(
        result: CollectorResult, target_task: str, phase: str,
        *, require_process_tree: bool = False,
    ) -> bool:
        return any(
            item.get("run_id") == run_id
            and item.get("task_id") == target_task
            and item.get("phase") == phase
            and item.get("permission") == permission
            and item.get("process") == {"pid": process.pid, "instance_id": process.instance_id}
            and item.get("complete") is True
            and item.get("task_finished") is True
            and (not require_process_tree or item.get("process_tree_complete") is True)
            for item in result.diagnostics.get("coverage", ())
            if isinstance(item, Mapping)
        )

    if not covered(positive_control, control_task_id, control_phase):
        return incomplete("positive control is not bound to a complete OS task/window")
    if not covered(observation, task_id, exercise_phase, require_process_tree=True):
        return incomplete("exercise lacks complete OS task/process-tree coverage")

    def matching(
        event: object, target_task: str, phase: str,
        *, require_target_process: bool = True,
    ) -> bool:
        if not isinstance(event, Mapping):
            return False
        return (
            event.get("run_id") == run_id
            and event.get("task_id") == target_task
            and event.get("phase") == phase
            and event.get("permission") == permission
            and (
                not require_target_process
                or event.get("process") == {"pid": process.pid, "instance_id": process.instance_id}
            )
        )

    if not any(
        matching(event, control_task_id, control_phase) and event.get("action") == "granted"
        for event in positive_control.observations
    ):
        return incomplete("no successful real OS permission access in positive control")
    if any(
        matching(event, task_id, exercise_phase, require_target_process=False)
        for event in observation.observations
    ):
        return OSAccessAssessment(OSAccessVerdict.UNAUTHORIZED_ACCESS, "native OS access observed in prohibited window")
    return OSAccessAssessment(OSAccessVerdict.NO_UNAUTHORIZED_ACCESS, "complete native OS window with successful positive control")


__all__ = [
    "OSAccessAssessment", "OSAccessVerdict", "OSPermissionAccess",
    "OSPermissionAccessSource", "OSPermissionAction", "OSPermissionCollector",
    "OSPermissionCoverage", "OSPermissionRead", "OSPermissionSourceInfo",
    "OSProcessIdentity", "assess_no_unauthorized_os_access",
]
