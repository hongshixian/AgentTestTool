"""Product-neutral AgentModel facade for OpenClaw's embedded CLI agent."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.environment.session import ControlledEnvironment
from agent_models.evidence import (
    EvidenceAuthority, EvidenceCorrelation, EvidencePhase, EvidenceRecord, EvidenceRequest,
    EvidenceSource, RequestContext,
)
from agent_models.interaction import InteractiveSession, PermissionPolicy
from agent_models.local_state import LocalStateRequest
from agent_models.openclaw.driver import OpenClawDriver, TurnOutcome, installed_version, resolve_executable
from agent_models.openclaw.mock_tool import OpenClawMockToolController
from agent_models.openclaw.profile import OpenClawTestProfile
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite

_DEFAULT_TIMEOUT = 240.0


class OpenClawAgentModel(AgentModel):
    """Run each turn as ``openclaw agent --local`` with a private config, home and state root.

    Headless runs have no per-call approval channel, so the declared ``PermissionPolicy``
    is mapped onto OpenClaw's config-layer ``tools.deny`` before every turn.
    """

    def __init__(self, *, workspace: Path, environment: ControlledEnvironment,
                 profile: OpenClawTestProfile) -> None:
        self._workspace = workspace
        self._environment = environment
        self.profile = profile
        self.mock_tool = OpenClawMockToolController(environment=environment)
        self._installation: InstallationResult | None = None
        self._driver: OpenClawDriver | None = None
        self._session_id: str | None = None
        self._turns: list[tuple[str, TurnResult]] = []
        self._prompt_sent = False
        self._closed = False

    @property
    def product(self) -> str:
        return "openclaw"

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
                self._installation = InstallationResult(False, f"openclaw executable not found: {self.profile.executable}")
            else:
                version = installed_version(executable)
                if version != self.profile.expected_version:
                    self._installation = InstallationResult(
                        False, f"OpenClaw {version or 'unknown'} is installed; {self.profile.expected_version} is required",
                        executable)
                else:
                    self._installation = InstallationResult(True, f"OpenClaw {version} is installed", executable)
        return self._installation

    def _ensure_driver(self) -> OpenClawDriver:
        if self._closed:
            raise RuntimeError("OpenClaw Model is closed")
        if self._driver is None:
            installation = self.check_installation()
            if not installation.installed or installation.executable is None:
                raise RuntimeError(installation.detail)
            if not self.profile.api_key:
                raise RuntimeError("OPENCLAW_TEST_API_KEY (or IIIS_API_KEY) is not configured")
            self._driver = OpenClawDriver(self.profile, executable=installation.executable, workspace=self._workspace)
            self._driver.mcp = self.mock_tool.server()
            self.environment.ledger.record("openclaw", "instance_ready", {
                "version": self.profile.expected_version, "model": self.profile.model_ref,
                "entry": "agent --local", "sandbox": "off (product default)",
                "permission_mapping": "config-layer tools.deny",
            })
        return self._driver

    def check_authentication(self) -> AuthResult:
        if not self.check_installation().installed:
            return AuthResult(AuthStatus.ERROR, self.check_installation().detail)
        try:
            driver = self._ensure_driver()
        except RuntimeError as error:
            return AuthResult(AuthStatus.ERROR, str(error))
        outcome = driver.run_turn("只回复 AUTH_OK。", session_id="auth_" + uuid.uuid4().hex[:12], timeout=300.0,
                                  policy=PermissionPolicy.DENY_UNAPPROVED, allow_tools=False)
        if outcome.ok and outcome.response.strip():
            return AuthResult(AuthStatus.AUTHENTICATED, "OpenClaw test model is available")
        detail = outcome.error or "OpenClaw test model did not complete"
        status = AuthStatus.UNAUTHENTICATED if "401" in detail or "authentication" in detail.lower() else AuthStatus.ERROR
        return AuthResult(status, self.environment.ledger.redact(detail)[-600:])

    def login(self) -> AuthResult:
        return AuthResult(AuthStatus.UNAUTHENTICATED,
                          "Configure OPENCLAW_TEST_API_KEY (or IIIS_API_KEY) for the dedicated test provider")

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
            raise NotImplementedError("OpenClaw has no public user/instance context selector")
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if permission_policy is PermissionPolicy.ASK:
            raise ValueError("headless OpenClaw turns cannot answer interactive permission requests")
        with self.environment.activity("send_prompt") as correlation:
            driver = self._ensure_driver()
            self._prompt_sent = True
            session_id = self._session_id or "ats_" + uuid.uuid4().hex[:16]
            outcome = driver.run_turn(prompt, session_id=session_id,
                                      timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
                                      policy=permission_policy, allow_tools=allow_tools,
                                      hidden_mock_tools=self.mock_tool.hidden_tool_names)
            result = self._turn_result(outcome, permission_policy, allow_tools)
            self._session_id = session_id
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
        raw = json.dumps({
            "tool_names": list(outcome.tool_names), "meta": outcome.meta,
            "permission_policy": policy.value, "allow_tools": allow_tools,
        }, ensure_ascii=False, default=str)
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
        self.environment.ledger.record("openclaw", "session_reset", {"run_id": self.environment.run_id})

    def start_session(self, *, timeout: float | None = None, allow_tools: bool = True,
                      permission_policy: PermissionPolicy = PermissionPolicy.ASK) -> InteractiveSession:
        raise NotImplementedError("OpenClaw interactive sessions are not implemented")

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        self._before_first_prompt()
        self.mock_tool.configure(profile, run_id=run_id)
        self._sync_mcp()

    def configure_mock_tools(self, suite: ToolSuite, *, run_id: str, initial_state: dict | None = None,
                             visible_tool_names: frozenset[str] | None = None, max_turns: int = 4) -> None:
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
                source = EvidenceSource(provider="openclaw_cli", channel="public_cli_json",
                                        authority=EvidenceAuthority.PRODUCT_PUBLIC_API, product="openclaw",
                                        product_version=self.profile.expected_version)
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
                        limitations=("Tool permissions are config-layer denials; no per-call approval evidence",),
                    ))
            records.extend(self.mock_tool.capture(request))
            records.extend(self.environment.capture(request))
            return tuple(records)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("OpenClaw has no implemented local state tamper adapter")

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("OpenClaw has no implemented local state restore adapter")

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
            raise BaseExceptionGroup("OpenClaw Model cleanup failed", errors)
