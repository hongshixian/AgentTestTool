"""CodeBuddy implementation of the public Agent Model facade."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.credentials import CodeBuddyCredentialProvider
from agent_models.codebuddy.driver import CodeBuddyDriver
from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
from agent_models.codebuddy.transport import CodeBuddyStdioTransport
from agent_models.evidence import EvidenceRecord, EvidenceRequest
from agent_models.result import AuthResult, AuthStatus, TurnResult


class CodeBuddyAgentModel(AgentModel):
    def __init__(
        self,
        *,
        workspace: Path,
        driver: CodeBuddyDriver,
        transport: CodeBuddyStdioTransport,
        credentials: CodeBuddyCredentialProvider,
        evidence: CodeBuddyCommandEvidenceProvider,
    ) -> None:
        self._workspace = workspace
        self.driver = driver
        self.transport = transport
        self.credentials = credentials
        self.evidence = evidence
        self._session_id = f"ats-{uuid.uuid4().hex}"
        self._has_started_session = False

    @property
    def product(self) -> str:
        return "codebuddy"

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            multi_turn=True,
            file_operations=True,
            isolated_configuration=self.credentials.isolated,
            trusted_evidence=self.evidence.is_available(),
        )

    def check_authentication(self) -> AuthResult:
        if not self.transport.is_available():
            return AuthResult(AuthStatus.ERROR, "找不到 codebuddy 命令")
        if not self.credentials.has_local_login_state():
            return AuthResult(AuthStatus.UNAUTHENTICATED, "未发现 CodeBuddy 本地登录状态")

        try:
            probe = self.transport.request(self.driver.AUTHENTICATION_PROBE, timeout=60.0)
        except subprocess.TimeoutExpired:
            return AuthResult(AuthStatus.ERROR, "CodeBuddy 认证探测超时")

        turn = self.driver.parse_turn(probe)
        if turn.completed:
            return AuthResult(AuthStatus.AUTHENTICATED, "CodeBuddy 认证探测成功")
        detail = turn.stderr.strip() or turn.response.strip() or "CodeBuddy 认证探测失败"
        return AuthResult(AuthStatus.UNAUTHENTICATED, detail[-500:])

    def login(self) -> AuthResult:
        return self.credentials.login()

    def send_prompt(self, prompt: str, *, timeout: float | None = None) -> TurnResult:
        response = self.transport.request(
            prompt,
            timeout=timeout,
            session_id=self._session_id,
            resume=self._has_started_session,
            allow_tools=True,
        )
        turn = self.driver.parse_turn(response)
        if turn.completed:
            self._has_started_session = True
        return turn

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        return self.evidence.capture(request)

    def close(self) -> None:
        self.transport.close()
        self.credentials.remove_test_session(self._session_id)
