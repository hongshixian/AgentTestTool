"""Product-neutral AgentModel facade for the OpenAI Codex CLI (`codex exec`)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.codex.driver import CodexDriver, TurnOutcome, installed_version, resolve_executable
from agent_models.codex.mock_tool import CodexMockToolController
from agent_models.codex.profile import CodexTestProfile
from agent_models.environment.session import ControlledEnvironment
from agent_models.evidence import (
    EvidenceAuthority, EvidenceCorrelation, EvidencePhase, EvidenceRecord, EvidenceRequest,
    EvidenceSource, RequestContext,
)
from agent_models.interaction import InteractiveSession, PermissionPolicy
from agent_models.local_state import LocalStateRequest
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite

_DEFAULT_TIMEOUT = 240.0


class CodexAgentModel(AgentModel):
    """Run each turn as ``codex exec`` (or ``exec resume``) with the operator's authenticated CODEX_HOME.

    Headless turns have no approval channel: ``approval_policy`` stays ``never`` and the
    declared ``PermissionPolicy`` selects the sandbox mode before every turn.
    """

    def __init__(self, *, workspace: Path, environment: ControlledEnvironment,
                 profile: CodexTestProfile) -> None:
        self._workspace = workspace
        self._environment = environment
        self.profile = profile
        self.mock_tool = CodexMockToolController(environment=environment)
        self._installation: InstallationResult | None = None
        self._version: str | None = None
        self._driver: CodexDriver | None = None
        self._session_id: str | None = None
        self._turns: list[tuple[str, TurnResult]] = []
        self._prompt_sent = False
        self._closed = False

    @property
    def product(self) -> str:
        return "codex"

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def environment(self) -> ControlledEnvironment:
        return self._environment

    @property
    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            multi_turn=True,
            file_operations=True,
            controlled_environment=True,
            mock_tools=True,
            multiple_mock_tools=True,
            independent_sessions=True,
            product_runtime_evidence=True,
            session_correlation_evidence=True,
        )

    def check_installation(self) -> InstallationResult:
        if self._installation is None:
            executable = resolve_executable(self.profile.executable)
            if executable is None:
                self._installation = InstallationResult(False, f"codex executable not found: {self.profile.executable}")
            else:
                self._version = installed_version(executable)
                if self._version is None:
                    self._installation = InstallationResult(False, "codex --version did not report a version",
                                                            str(executable))
                else:
                    self._installation = InstallationResult(True, f"Codex CLI {self._version} is installed",
                                                            str(executable))
        return self._installation

    def _ensure_driver(self) -> CodexDriver:
        if self._closed:
            raise RuntimeError("Codex Model is closed")
        if self._driver is None:
            installation = self.check_installation()
            if not installation.installed or installation.executable is None:
                raise RuntimeError(installation.detail)
            self._driver = CodexDriver(self.profile, executable=Path(installation.executable),
                                       workspace=self._workspace)
            self._driver.mcp = self.mock_tool.server()
            self.environment.ledger.record("codex", "instance_ready", {
                "version": self._version, "model": self.profile.model,
                "reasoning_effort": self.profile.reasoning_effort, "entry": "codex exec",
                "permission_mapping": "sandbox_mode with approval_policy=never",
            })
        return self._driver

    def check_authentication(self) -> AuthResult:
        if not self.check_installation().installed:
            return AuthResult(AuthStatus.ERROR, self.check_installation().detail)
        try:
            driver = self._ensure_driver()
        except RuntimeError as error:
            return AuthResult(AuthStatus.ERROR, str(error))
        outcome = driver.run_turn("只回复 AUTH_OK。", session_id=None, timeout=300.0,
                                  policy=PermissionPolicy.DENY_UNAPPROVED, allow_tools=False, ephemeral=True)
        if outcome.ok and outcome.response.strip():
            return AuthResult(AuthStatus.AUTHENTICATED, "Codex test model is available")
        detail = outcome.error or "Codex test model did not complete"
        lowered = detail.lower()
        status = (AuthStatus.UNAUTHENTICATED if "401" in detail or "login" in lowered or "auth" in lowered
                  else AuthStatus.ERROR)
        return AuthResult(status, self.environment.ledger.redact(detail)[-600:])

    def login(self) -> AuthResult:
        return AuthResult(AuthStatus.UNAUTHENTICATED,
                          "Authenticate Codex in the operator's CODEX_HOME; the evaluator never logs in")

    def send_prompt(
        self,
        prompt: str,
        *,
        context: RequestContext | None = None,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
    ) -> TurnResult:
        if context is not None:
            raise NotImplementedError("Codex has no public user/instance context selector")
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if permission_policy is PermissionPolicy.ASK:
            raise ValueError("headless Codex turns cannot answer interactive permission requests")
        with self.environment.activity("send_prompt") as correlation:
            driver = self._ensure_driver()
            self._prompt_sent = True
            outcome = driver.run_turn(prompt, session_id=self._session_id,
                                      timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
                                      policy=permission_policy, allow_tools=allow_tools)
            result = self._turn_result(outcome, permission_policy, allow_tools)
            if outcome.session_id:
                self._session_id = outcome.session_id
            self._turns.append((prompt, result))
            self.environment.record_turn(prompt, result, correlation_id=correlation)
            return result

    def _turn_result(self, outcome: TurnOutcome, policy: PermissionPolicy, allow_tools: bool) -> TurnResult:
        if outcome.timed_out:
            returncode = -1
        elif outcome.ok:
            returncode = 0
        else:
            returncode = outcome.returncode if outcome.returncode not in (None, 0) else 1
        stderr = outcome.error
        if not outcome.ok and outcome.stderr_tail and not outcome.timed_out:
            stderr = f"{stderr}\n{outcome.stderr_tail[-800:]}"
        raw = json.dumps({"tool_calls": outcome.tool_calls, "usage": outcome.usage,
                          "permission_policy": policy.value, "allow_tools": allow_tools},
                         ensure_ascii=False, default=str)
        return TurnResult(
            response=outcome.response,
            raw_output=self.environment.ledger.redact(raw),
            stderr=self.environment.ledger.redact(stderr),
            returncode=returncode,
            completed=outcome.ok,
            duration_seconds=outcome.duration_seconds,
            session_id=outcome.session_id,
        )

    def begin_independent_session(self) -> None:
        self._session_id = None
        self.environment.ledger.record("codex", "session_reset", {"run_id": self.environment.run_id})

    def start_session(self, *, timeout: float | None = None, allow_tools: bool = True,
                      permission_policy: PermissionPolicy = PermissionPolicy.ASK) -> InteractiveSession:
        raise NotImplementedError("Codex interactive sessions are not implemented")

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        self._before_first_prompt()
        self.mock_tool.configure(profile, run_id=run_id)
        self._sync_mcp()

    def configure_mock_tools(self, suite: ToolSuite, *, run_id: str, initial_state: dict | None = None,
                             visible_tool_names: frozenset[str] | None = None, max_turns: int = 4,
                             suite_type: str = "grey_box") -> None:
        self._before_first_prompt()
        self.mock_tool.configure_suite(suite, run_id=run_id, initial_state=initial_state,
                                       visible_tool_names=visible_tool_names)
        self._sync_mcp()

    def _before_first_prompt(self) -> None:
        if self._prompt_sent:
            raise RuntimeError("Mock tools must be configured before sending a prompt")

    def _sync_mcp(self) -> None:
        if self._driver is not None:
            self._driver.mcp = self.mock_tool.server()

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        with self.environment.activity("capture_evidence"):
            records: list[EvidenceRecord] = []
            if request.phase is EvidencePhase.AFTER:
                turns = [(prompt, result) for prompt, result in self._turns
                         if request.session_id is None or result.session_id == request.session_id]
                correlation = EvidenceCorrelation(
                    run_id=self.environment.run_id,
                    session_ids=tuple(sorted({result.session_id for _, result in turns if result.session_id})),
                )
                source = EvidenceSource(provider="codex_cli", channel="public_cli_jsonl",
                                        authority=EvidenceAuthority.PRODUCT_PUBLIC_API, product="codex",
                                        product_version=self._version)
                if turns:
                    records.append(EvidenceRecord(
                        "conversation_transcript", "runtime_evidence", request.phase,
                        self.environment.ledger.redact({"turns": [
                            {"prompt": prompt, "response": result.response, "session_id": result.session_id}
                            for prompt, result in turns]}),
                        source=source, correlation=correlation,
                        proves=("Observed user prompts and public CLI replies",),
                        limitations=("Does not prove hidden model or backend operations",),
                    ))
                    records.append(EvidenceRecord(
                        "api_cli_runtime_result", "runtime_evidence", request.phase,
                        {"turns": [{"completed": result.completed, "returncode": result.returncode,
                                    "duration_seconds": result.duration_seconds} for _, result in turns]},
                        source=source, correlation=correlation,
                        proves=("Public CLI completion state of observed turns",),
                        limitations=("Permissions are sandbox-mode selections; no per-call approval evidence",),
                    ))
            records.extend(self.mock_tool.capture(request))
            records.extend(self.environment.capture(request))
            return tuple(records)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("Codex has no implemented local state tamper adapter")

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("Codex has no implemented local state restore adapter")

    def close(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        try:
            self.environment.begin_shutdown(allow_active=True)
        except BaseException as error:
            errors.append(error)
        if self._driver is not None:
            self._driver.close()
        try:
            self.environment.close()
        except BaseException as error:
            errors.append(error)
        self._closed = True
        if errors:
            raise BaseExceptionGroup("Codex Model cleanup failed", errors)
