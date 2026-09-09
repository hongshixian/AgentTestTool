"""Public interface consumed by shared pytest cases."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType

from agent_models.capabilities import AgentCapabilities
from agent_models.evidence import EvidenceRecord, EvidenceRequest, JsonValue, RequestContext
from agent_models.environment.session import ControlledEnvironment
from agent_models.local_state import LocalStateRequest
from agent_models.interaction import InteractiveSession, PermissionPolicy
from agent_models.result import AuthResult, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite


class AgentModel(ABC):
    """Product-neutral facade for an Agent CLI under test."""

    @property
    def environment(self) -> ControlledEnvironment:
        """Return the evaluator-owned workspace, tools, scheduler and evidence store."""
        raise NotImplementedError("This product has no controlled environment adapter")

    def configure_mock_tools(self, suite: ToolSuite, *, run_id: str,
                             initial_state: dict[str, JsonValue] | None = None) -> None:
        """Connect multiple controlled tools through the product's public tool entry."""
        raise NotImplementedError("This product has no multiple-tool adapter")

    @property
    @abstractmethod
    def product(self) -> str:
        """Return the product identifier used by the factory."""

    @property
    @abstractmethod
    def workspace(self) -> Path:
        """Return the isolated workspace used by the CLI process."""

    @property
    @abstractmethod
    def capabilities(self) -> AgentCapabilities:
        """Return capabilities implemented by this product model."""

    @abstractmethod
    def check_installation(self) -> InstallationResult:
        """Determine whether the product CLI executable is installed."""

    @abstractmethod
    def check_authentication(self) -> AuthResult:
        """Actively determine whether the CLI can access its model service."""

    @abstractmethod
    def login(self) -> AuthResult:
        """Authenticate with credentials owned by the product provider."""

    @abstractmethod
    def send_prompt(
        self,
        prompt: str,
        *,
        context: RequestContext | None = None,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
    ) -> TurnResult:
        """Send one prompt with an explicit unattended permission policy."""

    @abstractmethod
    def start_session(
        self,
        *,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.ASK,
    ) -> InteractiveSession:
        """Start a long-lived product session over the public CLI protocol."""

    @abstractmethod
    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        """Collect evidence observable through public product interfaces."""

    @abstractmethod
    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        """Configure one deterministic mock tool before the session starts."""

    @abstractmethod
    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        """Snapshot, tamper, and restart an isolated product configuration."""

    @abstractmethod
    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        """Restore an isolated product configuration after a tamper test."""

    @abstractmethod
    def close(self) -> None:
        """Release resources owned by this model."""

    def __enter__(self) -> AgentModel:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
