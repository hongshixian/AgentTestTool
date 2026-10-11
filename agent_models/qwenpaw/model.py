"""Product-neutral AgentModel facade for QwenPaw's public REST/SSE console API."""

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
from agent_models.processes import ProcessCleanupError
from agent_models.qwenpaw.client import ApprovalDecision, QwenPawApiError, QwenPawClient, TurnOutcome, decide_approval
from agent_models.qwenpaw.mock_tool import QwenPawMockToolController
from agent_models.qwenpaw.profile import QwenPawTestProfile
from agent_models.qwenpaw.server import QwenPawServer, installed_version, resolve_executable
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite

_DEFAULT_TIMEOUT = 240.0
_USER_ID = "ats_user"


class QwenPawAgentModel(AgentModel):
    """Run each model against its own QwenPaw instance with STRICT, per-call approvals.

    STRICT routes every tool call through ``/api/approval``; the driver answers each
    one from the declared ``PermissionPolicy`` and archives the decision.
    """

    def __init__(self, *, workspace: Path, environment: ControlledEnvironment,
                 profile: QwenPawTestProfile) -> None:
        self._workspace = workspace
        self._environment = environment
        self.profile = profile
        self.mock_tool = QwenPawMockToolController(environment=environment)
        self._installation: InstallationResult | None = None
        self._server: QwenPawServer | None = None
        self._session_id: str | None = None
        self._turns: list[tuple[str, TurnResult]] = []
        self._decisions: list[tuple[str, ApprovalDecision]] = []
        self._prompt_sent = False
        self._setup_error: str | None = None
        self._closed = False
        self._cleanup_uncertain = False

    @property
    def product(self) -> str:
        return "qwenpaw"

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
            permission_event_evidence=True,
        )

    def check_installation(self) -> InstallationResult:
        if self._installation is None:
            executable = resolve_executable(self.profile.executable)
            if executable is None:
                self._installation = InstallationResult(False, f"qwenpaw executable not found: {self.profile.executable}")
            else:
                version = installed_version(executable)
                if version != self.profile.expected_version:
                    self._installation = InstallationResult(
                        False, f"QwenPaw {version or 'unknown'} is installed; {self.profile.expected_version} is required",
                        executable)
                else:
                    self._installation = InstallationResult(True, f"QwenPaw {version} is installed", executable)
        return self._installation

    def _client(self) -> QwenPawClient:
        if self._closed:
            raise RuntimeError("QwenPaw Model is closed")
        if self._setup_error is not None:
            raise RuntimeError(self._setup_error)
        if self._server is not None and self._server.client is not None:
            return self._server.client
        installation = self.check_installation()
        if not installation.installed or installation.executable is None:
            raise RuntimeError(installation.detail)
        server = QwenPawServer(self.profile, executable=installation.executable)
        self._server = server
        project_dir = str(self._workspace.resolve())
        try:
            # Tools act in the evaluator workspace; product state stays in the server's private root.
            client = server.start(agent_settings={"approval_level": "STRICT", "project_dir": project_dir})
            approval = client.get("/api/workspace/running-config").get("approval_level")
            effective_dir = client.get("/api/workspace/project-directory").get("path")
            if approval != "STRICT" or effective_dir != project_dir:
                raise RuntimeError(f"agent settings not applied (approval={approval}, project_dir={effective_dir})")
            self.mock_tool.register(client)
        except (QwenPawApiError, RuntimeError, TimeoutError, OSError) as error:
            self._setup_error = (f"QwenPaw instance setup failed: {error}; log tail: "
                                 f"{self.environment.ledger.redact(server.log_tail(600))}")
            raise RuntimeError(self._setup_error) from error
        self.environment.ledger.record("qwenpaw", "instance_ready", {
            "version": self.profile.expected_version, "model": self.profile.model,
            "approval_level": "STRICT", "sandbox": "product default",
        })
        return client

    def check_authentication(self) -> AuthResult:
        if not self.check_installation().installed:
            return AuthResult(AuthStatus.ERROR, self.check_installation().detail)
        try:
            client = self._client()
            outcome = self._run(client, "只回复 AUTH_OK。", session_id="auth_" + uuid.uuid4().hex[:12],
                                timeout=180.0, allow_tools=False, policy=PermissionPolicy.DENY_UNAPPROVED,
                                record=False)
        except ProcessCleanupError:
            self._cleanup_uncertain = True
            raise
        except RuntimeError as error:
            return AuthResult(AuthStatus.ERROR, str(error)[-600:])
        if outcome.transcript.status == "completed" and outcome.transcript.response_text.strip():
            return AuthResult(AuthStatus.AUTHENTICATED, "QwenPaw test model is available")
        detail = outcome.transcript.error or outcome.transport_error or "QwenPaw test model did not complete"
        return AuthResult(AuthStatus.UNAUTHENTICATED, self.environment.ledger.redact(detail)[-600:])

    def login(self) -> AuthResult:
        return AuthResult(AuthStatus.UNAUTHENTICATED,
                          "Configure QWENPAW_TEST_API_KEY (or IIIS_API_KEY) for the dedicated test provider")

    def _run(self, client: QwenPawClient, prompt: str, *, session_id: str, timeout: float,
             allow_tools: bool, policy: PermissionPolicy, record: bool = True) -> TurnOutcome:
        project_dir = self._workspace.resolve()

        def decide(item: dict) -> ApprovalDecision:
            return decide_approval(item, policy=policy, allow_tools=allow_tools,
                                   project_dir=project_dir, mock_configured=self.mock_tool.configured)

        def on_decision(decision: ApprovalDecision) -> None:
            if record:
                self._decisions.append((session_id, decision))
            self.environment.ledger.record("qwenpaw_permission", "decided", {
                "session_id": session_id, "request_id": decision.request_id, "tool_name": decision.tool_name,
                "tool_source": decision.tool_source, "target": decision.target,
                "decision": "approve" if decision.approve else "deny", "rule": decision.rule,
                "permission_policy": policy.value,
            })

        return client.run_turn(prompt, session_id=session_id, user_id=_USER_ID, timeout=timeout,
                               decide=decide, on_decision=on_decision)

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
            raise NotImplementedError("QwenPaw has no public user/instance context selector")
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if permission_policy is PermissionPolicy.ASK:
            raise ValueError("one-shot QwenPaw turns cannot answer interactive permission requests")
        with self.environment.activity("send_prompt") as correlation:
            client = self._client()
            self._prompt_sent = True
            session_id = self._session_id or "ats_" + uuid.uuid4().hex[:16]
            try:
                outcome = self._run(client, prompt, session_id=session_id,
                                    timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
                                    allow_tools=allow_tools, policy=permission_policy)
            except ProcessCleanupError:
                self._cleanup_uncertain = True
                raise
            result = self._turn_result(outcome)
            self._session_id = session_id
            self._turns.append((prompt, result))
            self.environment.record_turn(prompt, result, correlation_id=correlation)
            return result

    def _turn_result(self, outcome: TurnOutcome) -> TurnResult:
        transcript = outcome.transcript
        completed = (transcript.status == "completed" and not outcome.timed_out
                     and not outcome.transport_error)
        if outcome.timed_out:
            stderr = f"QwenPaw turn timed out; product stop accepted={outcome.stopped}"
            returncode = -1
        elif outcome.transport_error:
            stderr, returncode = outcome.transport_error, -1
        elif not completed:
            stderr, returncode = transcript.error or f"QwenPaw turn ended with status {transcript.status}", 1
        else:
            stderr, returncode = "", 0
        raw = json.dumps({
            "events": transcript.structural_events(),
            "tool_calls": transcript.tool_calls,
            "approvals": [{"tool_name": d.tool_name, "target": d.target,
                           "decision": "approve" if d.approve else "deny", "rule": d.rule}
                          for d in outcome.decisions],
        }, ensure_ascii=False)
        return TurnResult(
            response=transcript.response_text,
            raw_output=self.environment.ledger.redact(raw),
            stderr=self.environment.ledger.redact(stderr),
            returncode=returncode,
            completed=completed,
            duration_seconds=outcome.duration_seconds,
            session_id=outcome.session_id,
        )

    def begin_independent_session(self) -> None:
        self._session_id = None
        self.environment.ledger.record("qwenpaw", "session_reset", {"run_id": self.environment.run_id})

    def start_session(self, *, timeout: float | None = None, allow_tools: bool = True,
                      permission_policy: PermissionPolicy = PermissionPolicy.ASK) -> InteractiveSession:
        raise NotImplementedError("QwenPaw interactive sessions are not implemented")

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        self._before_first_prompt()
        self.mock_tool.configure(profile, run_id=run_id)
        self._register_mock_if_running()

    def configure_mock_tools(self, suite: ToolSuite, *, run_id: str, initial_state: dict | None = None,
                             visible_tool_names: frozenset[str] | None = None, max_turns: int = 4) -> None:
        self._before_first_prompt()
        self.mock_tool.configure_suite(suite, run_id=run_id, initial_state=initial_state,
                                       visible_tool_names=visible_tool_names)
        self._register_mock_if_running()

    def _before_first_prompt(self) -> None:
        if self._prompt_sent:
            raise RuntimeError("Mock tools must be configured before sending a prompt")

    def _register_mock_if_running(self) -> None:
        if self._server is not None and self._server.client is not None:
            self.mock_tool.register(self._server.client)

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
                source = EvidenceSource(provider="qwenpaw_console_api", channel="public_rest_sse",
                                        authority=EvidenceAuthority.PRODUCT_PUBLIC_API, product="qwenpaw",
                                        product_version=self.profile.expected_version)
                if turns:
                    records.append(EvidenceRecord(
                        "conversation_transcript", "runtime_evidence", request.phase,
                        self.environment.ledger.redact({"turns": [
                            {"prompt": prompt, "response": result.response, "session_id": result.session_id}
                            for prompt, result in turns]}),
                        source=source, correlation=correlation,
                        proves=("Observed user prompts and public console replies",),
                        limitations=("Does not prove hidden model or backend operations",),
                    ))
                    records.append(EvidenceRecord(
                        "api_cli_runtime_result", "runtime_evidence", request.phase,
                        {"turns": [{"completed": result.completed, "returncode": result.returncode,
                                    "duration_seconds": result.duration_seconds} for _, result in turns]},
                        source=source, correlation=correlation,
                        proves=("Public console completion state of observed turns",),
                        limitations=("SSE terminal status does not distinguish a stopped turn",),
                    ))
                decisions = [decision for session_id, decision in self._decisions
                             if request.session_id is None or session_id == request.session_id]
                if decisions:
                    records.append(EvidenceRecord(
                        "permission_decisions", "runtime_evidence", request.phase,
                        self.environment.ledger.redact({"decisions": [
                            {"tool_name": d.tool_name, "tool_source": d.tool_source, "target": d.target,
                             "decision": "approve" if d.approve else "deny", "rule": d.rule}
                            for d in decisions]}),
                        source=source, correlation=correlation,
                        proves=("Approval requests raised by QwenPaw and the evaluator's answers",),
                        limitations=("Covers tools routed through QwenPaw approvals only",),
                    ))
            records.extend(self.mock_tool.capture(request))
            records.extend(self.environment.capture(request))
            return tuple(records)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("QwenPaw has no implemented local state tamper adapter")

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("QwenPaw has no implemented local state restore adapter")

    def close(self) -> None:
        if self._closed:
            return
        if self._cleanup_uncertain:
            raise ProcessCleanupError("QwenPaw process tree could not be confirmed stopped; state was preserved")
        errors: list[BaseException] = []
        try:
            self.environment.begin_shutdown(allow_active=True)
        except BaseException as error:
            errors.append(error)
        if self._server is not None:
            try:
                self._server.close()
            except ProcessCleanupError:
                self._cleanup_uncertain = True
                raise
            except BaseException as error:
                errors.append(error)
        try:
            self.environment.close()
        except BaseException as error:
            errors.append(error)
        self._closed = True
        if errors:
            raise BaseExceptionGroup("QwenPaw Model cleanup failed", errors)
