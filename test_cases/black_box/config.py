"""Environment configuration derived from a case specification.

Previously environment setup information was scattered across five places:
spec.workspace_files, spec.metadata["input_config"], spec.initial_business_state,
two hard-coded frozensets in environment.py, and runtime file-writing in handlers.

EnvironmentConfig consolidates all of it: the builder reads this object, not
the raw spec, so every environment decision is data-driven and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_models import ToolSuite
from agent_models.evidence import JsonValue
from test_cases.black_box.models import BlackBoxCaseSpec, WorkspaceFileSpec
from test_cases.black_box.profiles import CaseProfile, profile_for


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    """Everything the builder needs to prepare one case's environment."""

    case_id: str
    workspace_root_name: str
    workspace_files: tuple[WorkspaceFileSpec, ...]
    initial_business_state: dict[str, JsonValue]
    observation_seconds: int | None
    profile: CaseProfile
    tool_suite: ToolSuite | None
    suite_metadata: dict[str, object]

    @staticmethod
    def from_spec(spec: BlackBoxCaseSpec, workspace_root: Path) -> EnvironmentConfig:
        """Derive the full environment configuration from a case specification.

        This is the single entry point that replaces all the scattered logic:
        - workspace_files from spec (already populated by specs.py for B-series)
        - profile from profiles.py (handler, tool decision, metrics split)
        - tool suite from tool_builders if profile says so
        - observation_seconds from metadata for B009
        """
        from test_cases.black_box.tool_builders import build_submission_tool_suite

        profile = profile_for(spec)
        tool_data = (
            build_submission_tool_suite(spec.case_id, profile.submission_metrics, spec.assertion_rules)
            if profile.has_submission_tool
            else None
        )

        return EnvironmentConfig(
            case_id=spec.case_id,
            workspace_root_name=workspace_root.name,
            workspace_files=spec.workspace_files,
            initial_business_state=dict(spec.initial_business_state),
            observation_seconds=spec.metadata.get("input_config", {}).get("Observation_Seconds")
            if isinstance(spec.metadata.get("input_config"), dict)
            else None,
            profile=profile,
            tool_suite=tool_data[0] if tool_data else None,
            suite_metadata=tool_data[1] if tool_data else {},
        )
