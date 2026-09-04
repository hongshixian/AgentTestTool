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
from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
from agent_models.codebuddy.transport import CodeBuddyStdioTransport
from agent_models.evidence import EvidenceRecord, EvidenceRequest, RequestContext
from agent_models.local_state import LocalStateAction, LocalStateRequest
from agent_models.result import AuthResult, AuthStatus, TurnResult
from agent_models.tools import MockToolProfile


class CodeBuddyAgentModel(AgentModel):
    def __init__(
        self,
        *,
        workspace: Path,
        driver: CodeBuddyDriver,
        transport: CodeBuddyStdioTransport,
        credentials: CodeBuddyCredentialProvider,
        evidence: CodeBuddyCommandEvidenceProvider,
        mock_tool: CodeBuddyMockToolController,
        local_state: CodeBuddyCommandLocalStateController,
    ) -> None:
        self._workspace = workspace
        self.driver = driver
        self.transport = transport
        self.credentials = credentials
        self.evidence = evidence
        self.mock_tool = mock_tool
        self.local_state = local_state
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
            dedicated_test_account=self.credentials.is_dedicated_test_account,
            external_observation=self.evidence.is_available(),
            mock_tools=True,
            local_state_control=self.local_state.is_available(),
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

    def send_prompt(
        self,
        prompt: str,
        *,
        context: RequestContext | None = None,
        timeout: float | None = None,
    ) -> TurnResult:
        if context is not None:
            raise RuntimeError("CodeBuddy CLI 未公开用户或实例身份上下文选择参数")
        response = self.transport.request(
            prompt,
            timeout=timeout,
            session_id=self._session_id,
            resume=self._has_started_session,
            allow_tools=True,
            extra_args=self.mock_tool.extra_args,
        )
        turn = self.driver.parse_turn(response)
        if turn.completed:
            self._has_started_session = True
        return turn

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        return self.evidence.capture(request) + self.mock_tool.capture(request)

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        if self._has_started_session:
            raise RuntimeError("必须在 Agent 会话开始前配置 Mock Tool")
        self.mock_tool.configure(profile, run_id=run_id)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        if self._has_started_session:
            raise RuntimeError("必须在 Agent 会话开始前准备本地状态")
        return self.local_state.execute(LocalStateAction.PREPARE, request)

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        return self.local_state.execute(LocalStateAction.RESTORE, request)

    def close(self) -> None:
        self.transport.close()
        self.mock_tool.close()
        self.credentials.remove_test_session(self._session_id)
