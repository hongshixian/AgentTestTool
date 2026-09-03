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
            from agent_models.codebuddy.credentials import CodeBuddyCredentialProvider
            from agent_models.codebuddy.driver import CodeBuddyDriver
            from agent_models.codebuddy.model import CodeBuddyAgentModel
            from agent_models.codebuddy.transport import CodeBuddyStdioTransport

            credentials = CodeBuddyCredentialProvider()
            transport = CodeBuddyStdioTransport(workspace=workspace)
            driver = CodeBuddyDriver()
            return CodeBuddyAgentModel(
                workspace=workspace,
                driver=driver,
                transport=transport,
                credentials=credentials,
            )

        raise ValueError(f"unsupported Agent CLI product: {product}")

