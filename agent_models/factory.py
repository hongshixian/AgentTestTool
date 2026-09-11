"""Factory for fully assembled product Agent Models."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence
from contextlib import AbstractContextManager
import os

from agent_models.base import AgentModel
from configs.environment import sensitive_environment_values


class AgentModelFactory:
    """Create the product model selected by a shared test run."""

    @staticmethod
    def worker_environment(product: str) -> AbstractContextManager[dict[str, str]]:
        """Provide product-owned local configuration isolation for one worker."""
        if product.strip().lower() == "codebuddy":
            from agent_models.codebuddy.worker_profile import isolated_worker_profile

            return isolated_worker_profile()
        raise ValueError(f"Worker isolation is not implemented for product: {product}")

    @staticmethod
    def parallel_block_reason(product: str) -> str | None:
        """Conservatively reject adapters with unisolated external helper state."""
        if product.strip().lower() != "codebuddy":
            return "Product worker isolation has not been implemented"
        if any(os.environ.get(name, "").strip() for name in (
            "CODEBUDDY_OBSERVATION_COMMAND", "CODEBUDDY_LOCAL_STATE_COMMAND",
        )):
            return "External product helpers do not declare worker isolation"
        return None

    @staticmethod
    def create(product: str, *, workspace: Path, evidence_directory: Path | None = None,
               assets_root: Path | None = None, run_id: str | None = None,
               secrets: Sequence[str] = ()) -> AgentModel:
        normalized = product.strip().lower()
        if normalized == "codebuddy":
            from agent_models.codebuddy.driver import CodeBuddyDriver
            from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
            from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
            from agent_models.codebuddy.memory import CodeBuddyMemoryStateController
            from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
            from agent_models.codebuddy.model import CodeBuddyAgentModel
            from agent_models.environment.session import ControlledEnvironment

            evidence = CodeBuddyCommandEvidenceProvider.from_environment(workspace=workspace)
            local_state = CodeBuddyCommandLocalStateController.from_environment(
                workspace=workspace
            )
            driver = CodeBuddyDriver(workspace=workspace)
            memory_state = CodeBuddyMemoryStateController(
                workspace=workspace,
                config_dir=driver.config_dir,
                dedicated_test_account=driver.is_dedicated_test_account,
            )
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
                memory_state=memory_state,
                environment=environment,
            )

        raise ValueError(f"unsupported Agent CLI product: {product}")
