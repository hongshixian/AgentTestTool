"""CodeBuddy implementation of the public Agent Model facade."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.driver import CodeBuddyDriver
from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider
from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
from agent_models.evidence import EvidenceRecord, EvidenceRequest, JsonValue, RequestContext
from agent_models.environment.session import ControlledEnvironment
from agent_models.local_state import LocalStateAction, LocalStateRequest
from agent_models.result import AuthResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite


class CodeBuddyAgentModel(AgentModel):
    def __init__(
        self,
        *,
        workspace: Path,
        driver: CodeBuddyDriver,
        evidence: CodeBuddyCommandEvidenceProvider,
        mock_tool: CodeBuddyMockToolController,
        local_state: CodeBuddyCommandLocalStateController,
        environment: ControlledEnvironment | None = None,
    ) -> None:
        self._workspace = workspace
        self.driver = driver
        self.evidence = evidence
        self.mock_tool = mock_tool
        self.local_state = local_state
        self._session_id = f"ats-{uuid.uuid4().hex}"
        self._has_started_session = False
        self._has_attempted_session = False
        self._environment = environment
        self._closed = False

    @property
    def environment(self) -> ControlledEnvironment:
        if self._environment is None:
            if self._closed:
                raise RuntimeError("Agent Model is closed")
            self._environment = ControlledEnvironment(self.workspace)
        return self._environment

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
            dedicated_test_account=self.driver.is_dedicated_test_account,
            external_observation=self.evidence.is_available(),
            security_boundary_observation=False,
            mock_tools=True,
            multiple_mock_tools=True,
            controlled_environment=True,
            local_state_control=self.local_state.is_available(),
        )

    def check_authentication(self) -> AuthResult:
        with self.environment.activity("authentication") as correlation:
            result = self._check_authentication()
            self.environment.ledger.record("agent_model", "authentication", asdict(result), correlation)
            return result

    def _check_authentication(self) -> AuthResult:
        return self.driver.check_authentication()

    def login(self) -> AuthResult:
        with self.environment.activity("login") as correlation:
            result = self.driver.login()
            self.environment.ledger.record("agent_model", "login", asdict(result), correlation)
            return result

    def send_prompt(
        self,
        prompt: str,
        *,
        context: RequestContext | None = None,
        timeout: float | None = None,
        allow_tools: bool = True,
    ) -> TurnResult:
        if context is not None:
            raise RuntimeError("CodeBuddy CLI 未公开用户或实例身份上下文选择参数")
        with self.environment.activity("send_prompt") as correlation:
            self._has_attempted_session = True
            self.environment.ledger.record("agent_model", "prompt",
                                           {"prompt": prompt, "session_id": self._session_id,
                                            "allow_tools": allow_tools}, correlation)
            try:
                turn = self.driver.send_prompt(
                    prompt, timeout=timeout, session_id=self._session_id,
                    resume=self._has_started_session, allow_tools=allow_tools,
                    extra_args=self.mock_tool.extra_args if allow_tools else (),
                )
            except subprocess.TimeoutExpired as error:
                def decode(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
                self.environment.ledger.record("agent_model", "turn_timeout",
                    {"stdout": decode(error.stdout), "stderr": decode(error.stderr)}, correlation)
                raise
            self.environment.record_turn(prompt, turn, correlation_id=correlation)
            if turn.completed:
                self._has_started_session = True
            return turn

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        with self.environment.activity("capture_evidence"):
            external_records = self.evidence.capture(request) if self.evidence.is_available() else ()
            records = external_records + self.mock_tool.capture(request) + self.environment.capture(request)
            self.environment.ledger.save_artifact(f"capture_{uuid.uuid4().hex}",
                                                  [asdict(record) for record in records])
            return records

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        if self._has_attempted_session:
            raise RuntimeError("必须在 Agent 会话开始前配置 Mock Tool")
        self.mock_tool.configure(profile, run_id=run_id)

    def configure_mock_tools(self, suite: ToolSuite, *, run_id: str,
                             initial_state: dict[str, JsonValue] | None = None) -> None:
        if self._has_attempted_session:
            raise RuntimeError("必须在 Agent 会话开始前配置 Mock Tool")
        self.mock_tool.configure_suite(suite, run_id=run_id, initial_state=initial_state)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        if self._has_started_session:
            raise RuntimeError("必须在 Agent 会话开始前准备本地状态")
        return self.local_state.execute(LocalStateAction.PREPARE, request)

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        return self.local_state.execute(LocalStateAction.RESTORE, request)

    def close(self) -> None:
        if self._closed:
            return
        if self._environment is not None:
            self._environment.begin_shutdown()
        errors: list[BaseException] = []
        for cleanup in (lambda: self.driver.close(session_id=self._session_id),
                        self.mock_tool.close,
                        self._environment.close if self._environment is not None else lambda: None):
            try:
                cleanup()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Agent Model cleanup failed", errors)
        self._closed = True
