"""Factory for fully assembled product Agent Models."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

from agent_models.base import AgentModel
from configs.environment import sensitive_environment_values


class AgentModelFactory:
    """Create the product model selected by a shared test run."""

    @staticmethod
    def create(product: str, *, workspace: Path, evidence_directory: Path | None = None,
               assets_root: Path | None = None, run_id: str | None = None,
               secrets: Sequence[str] = ()) -> AgentModel:
        normalized = product.strip().lower()
        if normalized == "codebuddy":
            from agent_models.codebuddy.driver import CodeBuddyDriver
            from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
            from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
            from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
            from agent_models.codebuddy.model import CodeBuddyAgentModel
            from agent_models.environment.session import ControlledEnvironment

            evidence = CodeBuddyCommandEvidenceProvider.from_environment(workspace=workspace)
            local_state = CodeBuddyCommandLocalStateController.from_environment(
                workspace=workspace
            )
            driver = CodeBuddyDriver(workspace=workspace)
            environment = ControlledEnvironment(workspace, evidence_directory=evidence_directory,
                                                assets_root=assets_root, run_id=run_id,
                                                secrets=(*sensitive_environment_values(), *secrets))
            mock_tool = CodeBuddyMockToolController(workspace=workspace, environment=environment)
            return CodeBuddyAgentModel(
                workspace=workspace,
                driver=driver,
                evidence=evidence,
                mock_tool=mock_tool,
                local_state=local_state,
                environment=environment,
            )

        raise ValueError(f"unsupported Agent CLI product: {product}")
