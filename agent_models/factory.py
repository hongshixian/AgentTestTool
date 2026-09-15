"""Factory for fully assembled product Agent Models."""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import AbstractContextManager
from pathlib import Path

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
               secrets: Sequence[str] = (), test_case_id: str | None = None,
               enable_network_capture: bool = True) -> AgentModel:
        normalized = product.strip().lower()
        if normalized == "codebuddy":
            from agent_models.codebuddy.driver import CodeBuddyDriver
            from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
            from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
            from agent_models.codebuddy.memory import CodeBuddyMemoryStateController
            from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
            from agent_models.codebuddy.model import CodeBuddyAgentModel
            from agent_models.environment.session import ControlledEnvironment
            from evidence_collectors.base import CollectionContext
            from evidence_collectors.manager import EvidenceCollectorManager
            from evidence_collectors.network import HttpsMitmCollector

            evidence = CodeBuddyCommandEvidenceProvider.from_environment(workspace=workspace)
            local_state = CodeBuddyCommandLocalStateController.from_environment(
                workspace=workspace
            )
            effective_secrets = (*sensitive_environment_values(), *secrets)
            environment = ControlledEnvironment(
                workspace,
                evidence_directory=evidence_directory,
                assets_root=assets_root,
                run_id=run_id,
                secrets=effective_secrets,
            )
            collector_manager: EvidenceCollectorManager | None = None
            launch_environment: dict[str, str] = {}
            try:
                if enable_network_capture:
                    collector_manager = EvidenceCollectorManager((HttpsMitmCollector(),))
                    launch = collector_manager.prepare(
                        CollectionContext(
                            run_id=environment.run_id,
                            test_case_id=test_case_id or "unassigned-test-case",
                            product="codebuddy",
                            workspace=workspace,
                            evidence_dir=environment.evidence_directory,
                            secrets=effective_secrets,
                            acquisition_methods=("Q04-network-interception",),
                        )
                    )
                    collector_manager.start()
                    launch_environment = dict(launch.environment_overrides)
                driver = CodeBuddyDriver(
                    workspace=workspace,
                    process_environment_overrides=launch_environment,
                )
                memory_state = CodeBuddyMemoryStateController(
                    workspace=workspace,
                    config_dir=driver.config_dir,
                    dedicated_test_account=driver.is_dedicated_test_account,
                )
                mock_tool = CodeBuddyMockToolController(
                    workspace=workspace,
                    environment=environment,
                )
                return CodeBuddyAgentModel(
                    workspace=workspace,
                    driver=driver,
                    evidence=evidence,
                    mock_tool=mock_tool,
                    local_state=local_state,
                    memory_state=memory_state,
                    environment=environment,
                    collector_manager=collector_manager,
                    test_case_id=test_case_id,
                )
            except BaseException as primary_error:
                cleanup_errors: list[BaseException] = []
                if collector_manager is not None:
                    try:
                        collector_manager.close()
                    except BaseException as error:
                        cleanup_errors.append(error)
                try:
                    environment.close()
                except BaseException as error:
                    cleanup_errors.append(error)
                if cleanup_errors:
                    raise BaseExceptionGroup(
                        "CodeBuddy evidence collector setup and cleanup failed",
                        [primary_error, *cleanup_errors],
                    )
                raise

        raise ValueError(f"unsupported Agent CLI product: {product}")
