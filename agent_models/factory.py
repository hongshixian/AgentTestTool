"""Factory for fully assembled product Agent Models."""

from __future__ import annotations

from pathlib import Path

from agent_models.base import AgentModel


class AgentModelFactory:
    """Create the product model selected by a shared test run."""

    @staticmethod
    def create(product: str, *, workspace: Path) -> AgentModel:
        normalized = product.strip().lower()
        if normalized == "codebuddy":
            from agent_models.codebuddy.context import CodeBuddyRequestContextAdapter
            from agent_models.codebuddy.credentials import CodeBuddyCredentialProvider
            from agent_models.codebuddy.driver import CodeBuddyDriver
            from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
            from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
            from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
            from agent_models.codebuddy.model import CodeBuddyAgentModel
            from agent_models.codebuddy.transport import CodeBuddyStdioTransport

            credentials = CodeBuddyCredentialProvider()
            evidence = CodeBuddyCommandEvidenceProvider.from_environment(workspace=workspace)
            mock_tool = CodeBuddyMockToolController(workspace=workspace)
            request_context = CodeBuddyRequestContextAdapter.from_environment()
            local_state = CodeBuddyCommandLocalStateController.from_environment(
                workspace=workspace
            )
            transport = CodeBuddyStdioTransport(workspace=workspace)
            driver = CodeBuddyDriver()
            return CodeBuddyAgentModel(
                workspace=workspace,
                driver=driver,
                transport=transport,
                credentials=credentials,
                evidence=evidence,
                mock_tool=mock_tool,
                request_context=request_context,
                local_state=local_state,
            )

        raise ValueError(f"unsupported Agent CLI product: {product}")
