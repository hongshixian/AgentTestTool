"""Typed contracts for black-box case execution and observations."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from agent_models.evidence import JsonValue
from agent_models.environment.session import EnvironmentSnapshot
from agent_models.environment.workspace import WorkspaceSnapshot


def _frozen_mapping(value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    return MappingProxyType(copy.deepcopy(dict(value)))


@dataclass(frozen=True, slots=True)
class WorkspaceFileSpec:
    path: str
    content: str = ""
    asset: str | None = None
    mode: int | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("workspace file path must be nonempty")
        if self.asset is not None and (not self.asset.strip() or self.content):
            raise ValueError("workspace file must choose inline content or one asset")
        if self.mode is not None and not 0 <= self.mode <= 0o7777:
            raise ValueError("workspace file mode is invalid")


@dataclass(frozen=True, slots=True)
class PublicStepSpec:
    phase_id: str
    prompt: str
    allow_tools: bool = True
    permission_policy: str = "deny_unapproved"

    def __post_init__(self) -> None:
        if not self.phase_id.strip() or not self.prompt.strip():
            raise ValueError("public step phase and prompt must be nonempty")


@dataclass(frozen=True, slots=True)
class AssertionRule:
    metric: str
    operator: str
    expected: JsonValue

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("assertion metric must be nonempty")
        if self.operator not in {"eq", "ne", "lt", "le", "gt", "ge", "contains", "not_contains"}:
            raise ValueError(f"unsupported assertion operator: {self.operator}")


@dataclass(frozen=True, slots=True)
class BlackBoxCaseSpec:
    case_id: str
    title: str
    repeat_count: int
    timeout_seconds: float
    steps: tuple[PublicStepSpec, ...] = ()
    workspace_files: tuple[WorkspaceFileSpec, ...] = ()
    initial_business_state: Mapping[str, JsonValue] = field(default_factory=dict)
    assertion_rules: tuple[AssertionRule, ...] = ()
    marker: str = ""
    public_marker: str = ""
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.startswith("B") or not self.case_id[1:].isdigit():
            raise ValueError("black-box case ID must use B followed by digits")
        if not self.title.strip():
            raise ValueError("black-box case title must be nonempty")
        if isinstance(self.repeat_count, bool) or self.repeat_count < 1:
            raise ValueError("repeat_count must be a positive integer")
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        object.__setattr__(self, "initial_business_state", _frozen_mapping(self.initial_business_state))
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class PreparedBlackBoxEnvironment:
    spec: BlackBoxCaseSpec
    repeat_index: int
    run_id: str
    workspace: Path
    original: EnvironmentSnapshot
    baseline: EnvironmentSnapshot


@dataclass(frozen=True, slots=True)
class PublicTurnObservation:
    phase_id: str
    response: str
    returncode: int
    completed: bool
    duration_seconds: float
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class BlackBoxExecutionResult:
    turns: tuple[PublicTurnObservation, ...]
    metrics: Mapping[str, JsonValue] = field(default_factory=dict)
    public_objects: tuple[JsonValue, ...] = ()
    attachments: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", _frozen_mapping(self.metrics))
        object.__setattr__(self, "public_objects", tuple(copy.deepcopy(self.public_objects)))
        object.__setattr__(self, "attachments", tuple(Path(path) for path in self.attachments))


@dataclass(frozen=True, slots=True)
class PublicObservation:
    turns: tuple[PublicTurnObservation, ...]
    output_text: str
    public_objects: tuple[JsonValue, ...]
    attachments: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class FileObservation:
    before: WorkspaceSnapshot
    after: WorkspaceSnapshot
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ControlObservation:
    run_id: str
    case_id: str
    repeat_index: int
    collector_ready: bool
    positive_control_ok: bool
    collection_complete: bool
    dropped_event_count: int = 0


@dataclass(frozen=True, slots=True)
class BlackBoxEvidence:
    public: PublicObservation
    files: FileObservation
    control: ControlObservation
    business_state_before: Mapping[str, JsonValue]
    business_state_after: Mapping[str, JsonValue]
    metrics: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "business_state_before", _frozen_mapping(self.business_state_before))
        object.__setattr__(self, "business_state_after", _frozen_mapping(self.business_state_after))
        object.__setattr__(self, "metrics", _frozen_mapping(self.metrics))
