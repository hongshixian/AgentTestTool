"""Product-neutral contracts for long-lived Agent CLI interaction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from agent_models.evidence import JsonValue
from agent_models.result import TurnResult


class AgentEventType(str, Enum):
    """Observable events emitted by a long-lived Agent CLI session."""

    SESSION_STARTED = "session_started"
    USER_INPUT = "user_input"
    TEXT = "text"
    TEXT_DELTA = "text_delta"
    THINKING = "thinking"
    THINKING_DELTA = "thinking_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_DECISION = "permission_decision"
    CONTROL_REQUEST = "control_request"
    CONTROL_RESPONSE = "control_response"
    MCP_STATUS = "mcp_status"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    TURN_COMPLETED = "turn_completed"
    STDERR = "stderr"
    PROTOCOL_ERROR = "protocol_error"
    SESSION_EXITED = "session_exited"
    RAW = "raw"


class PermissionDecision(str, Enum):
    """Decisions a test can return to a product-native permission request."""

    ALLOW = "allow"
    DENY = "deny"
    CANCEL = "cancel"


class PermissionPolicy(str, Enum):
    """Initial product permission strategy for an interactive session."""

    ASK = "ask"
    DENY_UNAPPROVED = "deny_unapproved"
    ALLOW_WORKSPACE_EDITS = "allow_workspace_edits"
    BYPASS = "bypass"


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """One normalized event in the exact order observed by the test driver."""

    sequence: int
    event_type: AgentEventType
    observed_at: str
    monotonic_seconds: float
    session_id: str | None = None
    request_id: str | None = None
    turn_id: str | None = None
    text: str = ""
    data: JsonValue = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TurnHandle:
    """Correlate one input with the events observed after it was sent."""

    turn_id: str
    prompt: str
    after_sequence: int
    sent_at_monotonic: float


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Normalized response to an interactive control request."""

    request_id: str
    success: bool
    data: JsonValue = field(default_factory=dict)
    error: str = ""


EventPredicate: TypeAlias = Callable[[AgentEvent], bool]


class InteractiveSession(ABC):
    """Synchronous API for a product driver's long-lived CLI process."""

    @property
    @abstractmethod
    def session_id(self) -> str:
        """Return the product session identifier requested by the driver."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Return whether the product process is still running."""

    @property
    @abstractmethod
    def events(self) -> tuple[AgentEvent, ...]:
        """Return a stable snapshot of all normalized events."""

    @abstractmethod
    def send_input(self, prompt: str) -> TurnHandle:
        """Send a new user turn without restarting the CLI process."""

    @abstractmethod
    def wait_for_event(
        self,
        event_types: AgentEventType | Collection[AgentEventType],
        *,
        timeout: float,
        after_sequence: int = 0,
        predicate: EventPredicate | None = None,
    ) -> AgentEvent:
        """Wait deterministically for a matching event after a sequence number."""

    @abstractmethod
    def wait_for_completion(
        self,
        turn: TurnHandle,
        *,
        timeout: float | None = None,
    ) -> TurnResult:
        """Wait for and normalize the terminal result of one user turn."""

    @abstractmethod
    def respond_to_confirmation(
        self,
        event: AgentEvent,
        decision: PermissionDecision,
        *,
        reason: str,
        updated_input: dict[str, JsonValue] | None = None,
    ) -> None:
        """Answer one product-native permission request by request ID."""

    @abstractmethod
    def steer(
        self,
        text: str,
        *,
        timeout: float | None = None,
        expected_request_id: str | None = None,
    ) -> ControlResult:
        """Inject guidance into the currently running Agent turn."""

    @abstractmethod
    def interrupt_task(
        self,
        *,
        reason: str,
        timeout: float | None = None,
    ) -> ControlResult:
        """Request cancellation of the current Agent turn."""

    @abstractmethod
    def close(self) -> None:
        """Close stdin and prove that the child process has terminated."""

    def __enter__(self) -> InteractiveSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
