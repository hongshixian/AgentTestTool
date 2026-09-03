"""Capabilities exposed consistently to shared test cases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    """Feature switches used to decide which shared cases apply."""

    authentication: bool = True
    prompt: bool = True
    multi_turn: bool = False

