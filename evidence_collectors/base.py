"""Product-neutral lifecycle contracts for evidence collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
FrozenJsonValue: TypeAlias = (
    JsonScalar
    | tuple["FrozenJsonValue", ...]
    | frozenset["FrozenJsonValue"]
    | Mapping[str, "FrozenJsonValue"]
)


def utc_now() -> datetime:
    """Return an aware timestamp suitable for cross-collector correlation."""

    return datetime.now(timezone.utc)


def _nonempty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a nonempty string")
    return value


def _string_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{field_name} must contain nonempty strings")
    return tuple(values)


def _freeze_json_value(value: object) -> FrozenJsonValue:
    """Detach and recursively freeze JSON-like diagnostic containers."""

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("nested collector diagnostics must use string keys")
        return MappingProxyType(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("collector diagnostics values must be JSON-like")


class CollectorStatus(str, Enum):
    """Collection status compatible with ``agent_models.evidence.EvidenceStatus``."""

    AVAILABLE = "available"
    MISSING = "missing"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNVERIFIED = "unverified"


class CollectorHealthState(str, Enum):
    """Operational health, kept separate from whether evidence was available."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class CollectorHealth:
    state: CollectorHealthState = CollectorHealthState.HEALTHY
    detail: str | None = None
    lost_record_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.state, CollectorHealthState):
            raise ValueError("collector health state must use CollectorHealthState")
        if self.detail is not None and not self.detail.strip():
            raise ValueError("collector health detail must be nonempty when provided")
        if (
            isinstance(self.lost_record_count, bool)
            or not isinstance(self.lost_record_count, int)
            or self.lost_record_count < 0
        ):
            raise ValueError("lost_record_count must be a nonnegative integer")

    @property
    def healthy(self) -> bool:
        return self.state is CollectorHealthState.HEALTHY


@dataclass(frozen=True, slots=True)
class CollectionContext:
    """Run-scoped information shared by every evidence collector."""

    run_id: str
    test_case_id: str
    product: str
    workspace: Path
    evidence_dir: Path
    repeat_index: int = 1
    session_id: str | None = None
    evidence_categories: tuple[str, ...] = ()
    acquisition_methods: tuple[str, ...] = ()
    secrets: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _nonempty(self.run_id, "run_id")
        _nonempty(self.test_case_id, "test_case_id")
        _nonempty(self.product, "product")
        if (
            isinstance(self.repeat_index, bool)
            or not isinstance(self.repeat_index, int)
            or self.repeat_index < 1
        ):
            raise ValueError("repeat_index must be a positive integer")
        if self.session_id is not None:
            _nonempty(self.session_id, "session_id")
        object.__setattr__(self, "workspace", Path(self.workspace).resolve())
        object.__setattr__(self, "evidence_dir", Path(self.evidence_dir).resolve())
        object.__setattr__(
            self,
            "evidence_categories",
            _string_tuple(self.evidence_categories, "evidence_categories"),
        )
        object.__setattr__(
            self,
            "acquisition_methods",
            _string_tuple(self.acquisition_methods, "acquisition_methods"),
        )
        object.__setattr__(self, "secrets", _string_tuple(self.secrets, "secrets"))


@dataclass(frozen=True, slots=True)
class CollectorLaunchConfig:
    """Process launch changes requested by a prepared collector."""

    environment_overrides: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        overrides = dict(self.environment_overrides)
        if any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            for key, value in overrides.items()
        ):
            raise ValueError("environment overrides must map nonempty names to strings")
        object.__setattr__(self, "environment_overrides", MappingProxyType(overrides))


@dataclass(frozen=True, slots=True)
class EvidenceCursor:
    """Opaque collector-local position marking an observation boundary."""

    collector_name: str
    value: str
    observed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _nonempty(self.collector_name, "collector_name")
        _nonempty(self.value, "cursor value")
        if self.observed_at.tzinfo is None:
            raise ValueError("cursor observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CollectionCheckpoint:
    """A synchronized set of collector-local cursors."""

    label: str
    cursors: Mapping[str, EvidenceCursor]
    observed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _nonempty(self.label, "checkpoint label")
        cursors = dict(self.cursors)
        for name, cursor in cursors.items():
            _nonempty(name, "checkpoint collector name")
            if not isinstance(cursor, EvidenceCursor) or cursor.collector_name != name:
                raise ValueError("checkpoint cursors must match their collector names")
        if self.observed_at.tzinfo is None:
            raise ValueError("checkpoint observed_at must be timezone-aware")
        object.__setattr__(self, "cursors", MappingProxyType(cursors))


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    """Bounded interval used for incremental evidence collection."""

    start: CollectionCheckpoint
    end: CollectionCheckpoint
    label: str

    def __post_init__(self) -> None:
        _nonempty(self.label, "observation window label")
        if self.end.observed_at < self.start.observed_at:
            raise ValueError("observation window end cannot precede its start")

    def cursors_for(self, collector_name: str) -> tuple[EvidenceCursor, EvidenceCursor]:
        """Return the collector-local boundaries, failing on incomplete windows."""

        try:
            return self.start.cursors[collector_name], self.end.cursors[collector_name]
        except KeyError as exc:
            raise KeyError(
                f"observation window has no cursor for collector {collector_name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class CollectorResult:
    """One collector's bounded observations and explicit quality diagnosis."""

    collector_name: str
    status: CollectorStatus
    health: CollectorHealth
    observations: tuple[JsonValue, ...] = ()
    started_at: datetime = field(default_factory=utc_now)
    ended_at: datetime = field(default_factory=utc_now)
    limitations: tuple[str, ...] = ()
    diagnostics: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nonempty(self.collector_name, "collector_name")
        if not isinstance(self.status, CollectorStatus):
            raise ValueError("collector result status must use CollectorStatus")
        if not isinstance(self.health, CollectorHealth):
            raise ValueError("collector result health must use CollectorHealth")
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("collector result timestamps must be timezone-aware")
        if self.ended_at < self.started_at:
            raise ValueError("collector result end cannot precede its start")
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(
            self, "limitations", _string_tuple(self.limitations, "limitations")
        )
        diagnostics = dict(self.diagnostics)
        if any(not isinstance(key, str) or not key for key in diagnostics):
            raise ValueError("collector diagnostics must use nonempty string keys")
        object.__setattr__(
            self,
            "diagnostics",
            MappingProxyType(
                {key: _freeze_json_value(value) for key, value in diagnostics.items()}
            ),
        )
        if self.status is CollectorStatus.AVAILABLE and not self.health.healthy:
            raise ValueError("available evidence requires a healthy collector")


class EvidenceCollector(ABC):
    """Lifecycle contract implemented by sidecar, stream, and snapshot collectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable name used for cursors, results, and diagnostics."""

    @abstractmethod
    def prepare(self, context: CollectionContext) -> CollectorLaunchConfig:
        """Allocate resources and return environment changes needed before launch."""

    @abstractmethod
    def start(self) -> None:
        """Start observing before the tested Agent process begins its operation."""

    @abstractmethod
    def checkpoint(self, label: str) -> EvidenceCursor:
        """Mark and return the collector's current observation position."""

    @abstractmethod
    def collect(self, window: ObservationWindow) -> CollectorResult:
        """Return observations bounded by two manager checkpoints."""

    @abstractmethod
    def drain(self, timeout_seconds: float) -> CollectorResult:
        """Flush pending observations without closing the collector."""

    @abstractmethod
    def close(self) -> None:
        """Release collector resources; implementations should make this idempotent."""


__all__ = [
    "CollectionCheckpoint",
    "CollectionContext",
    "CollectorHealth",
    "CollectorHealthState",
    "CollectorLaunchConfig",
    "CollectorResult",
    "CollectorStatus",
    "EvidenceCollector",
    "EvidenceCursor",
    "JsonValue",
    "ObservationWindow",
    "utc_now",
]
