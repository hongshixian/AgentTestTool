"""Unified interface for Agent CLI products under test."""

from agent_models.base import AgentModel
from agent_models.evidence import (
    EvidenceBundle,
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidencePhase,
    EvidenceRecord,
    EvidenceRequirement,
    EvidenceRequest,
    EvidenceSource,
    EvidenceStatus,
    RequestContext,
    TranscriptTurn,
)
from agent_models.factory import AgentModelFactory
from agent_models.local_state import LocalStateAction, LocalStateKind, LocalStateRequest
from agent_models.interaction import (
    AgentEvent,
    AgentEventType,
    BackgroundTaskControlResult,
    BackgroundTaskHandle,
    BackgroundTaskObservation,
    ControlResult,
    InteractiveSession,
    PermissionDecision,
    PermissionResponse,
    PermissionPolicy,
    TurnHandle,
)
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolDefinition, ToolEffect, ToolResponse, ToolSuite

__all__ = [
    "AgentModel",
    "AgentModelFactory",
    "AuthResult",
    "AuthStatus",
    "InstallationResult",
    "AgentEvent",
    "AgentEventType",
    "BackgroundTaskControlResult",
    "BackgroundTaskHandle",
    "BackgroundTaskObservation",
    "ControlResult",
    "InteractiveSession",
    "PermissionDecision",
    "PermissionResponse",
    "PermissionPolicy",
    "TurnHandle",
    "EvidenceBundle",
    "EvidenceAuthority",
    "EvidenceCorrelation",
    "EvidencePhase",
    "EvidenceRecord",
    "EvidenceRequirement",
    "EvidenceRequest",
    "EvidenceSource",
    "EvidenceStatus",
    "RequestContext",
    "MockToolProfile",
    "ToolDefinition",
    "ToolEffect",
    "ToolResponse",
    "ToolSuite",
    "LocalStateAction",
    "LocalStateKind",
    "LocalStateRequest",
    "TranscriptTurn",
    "TurnResult",
]
