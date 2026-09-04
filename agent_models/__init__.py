"""Unified interface for Agent CLI products under test."""

from agent_models.base import AgentModel
from agent_models.evidence import (
    EvidenceBundle,
    EvidencePhase,
    EvidenceRecord,
    EvidenceRequest,
    RequestContext,
    TranscriptTurn,
)
from agent_models.factory import AgentModelFactory
from agent_models.result import AuthResult, AuthStatus, TurnResult

__all__ = [
    "AgentModel",
    "AgentModelFactory",
    "AuthResult",
    "AuthStatus",
    "EvidenceBundle",
    "EvidencePhase",
    "EvidenceRecord",
    "EvidenceRequest",
    "RequestContext",
    "TranscriptTurn",
    "TurnResult",
]
