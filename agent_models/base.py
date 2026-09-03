"""Public interface consumed by shared pytest cases."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType

from agent_models.capabilities import AgentCapabilities
from agent_models.result import AuthResult, TurnResult


class AgentModel(ABC):
    """Product-neutral facade for an Agent CLI under test."""

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
    def check_authentication(self) -> AuthResult:
        """Actively determine whether the CLI can access its model service."""

    @abstractmethod
    def login(self) -> AuthResult:
        """Authenticate with credentials owned by the product provider."""

    @abstractmethod
    def send_prompt(self, prompt: str, *, timeout: float | None = None) -> TurnResult:
        """Send one prompt over the product's standard input channel."""

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

