"""Product-neutral AgentModel facade for the OpenCode CLI."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlsplit
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.evidence import (
    EvidenceAuthority, EvidenceCorrelation, EvidencePhase, EvidenceRecord, EvidenceStatus,
    EvidenceRequest, EvidenceSource, RequestContext,
)
from agent_models.environment.session import ControlledEnvironment
from agent_models.interaction import InteractiveSession, PermissionPolicy
from agent_models.local_state import LocalStateRequest
from agent_models.opencode.driver import OpenCodeDriver
from agent_models.opencode.hooks.capture import OpenCodeHookCapture
from agent_models.opencode.network_trace import OpenCodeNetworkTrace
from agent_models.opencode.mock_tool import OpenCodeMockToolController
from agent_models.opencode.profile import DEFAULT_TEST_MODEL, OpenCodeTestProfile
from agent_models.opencode.trace_adapter import OpenCodeTraceAdapter
from agent_models.processes import ProcessCleanupError
from agent_models.result import AuthResult, AuthStatus, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite
from evidence_collectors.base import CollectorResult, ObservationWindow
from evidence_collectors.manager import EvidenceCollectorManager


class OpenCodeAgentModel(AgentModel):
    """Keep product details out of shared black-, grey- and white-box cases."""

    def __init__(
        self,
        *,
        workspace: Path,
        environment: ControlledEnvironment,
        profile: OpenCodeTestProfile,
        driver: OpenCodeDriver | None = None,
        collector_manager: EvidenceCollectorManager | None = None,
        hook_capture: OpenCodeHookCapture | None = None,
    ) -> None:
        self._workspace = workspace
        self._environment = environment
        self.profile = profile
        self.driver = driver or OpenCodeDriver(workspace=workspace, profile=profile)
        self.mock_tool = OpenCodeMockToolController(workspace=workspace, environment=environment)
        self._session_id: str | None = None
        self._execution_path: str | None = None
        self._closed = False
        self._cleanup_uncertain = False
        self._turns: list[tuple[str, TurnResult]] = []
        self._trace_adapter = OpenCodeTraceAdapter()
        self._collector_manager = collector_manager
        self._hook_capture = hook_capture
        self._hook_windows: list[tuple[str | None, int, str]] = []
        self._network_windows: list[tuple[str | None, CollectorResult, str, str, str, str]] = []
        self._network_trace = OpenCodeNetworkTrace()
        self._interactive_sessions: list[InteractiveSession] = []

    @property
    def product(self) -> str:
        return "opencode"

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
            interactive_session=True,
            product_runtime_evidence=True,
            session_correlation_evidence=True,
            network_traffic_evidence=self._collector_manager is not None,
            reconstructed_agent_trace=(
                self._collector_manager is not None
                and self._hook_capture is not None
                and self.profile.model == DEFAULT_TEST_MODEL
            ),
        )

    def check_installation(self) -> InstallationResult:
        return self.driver.check_installation()

    def check_authentication(self) -> AuthResult:
        try:
            return self.driver.check_authentication()
        except ProcessCleanupError:
            self._cleanup_uncertain = True
            raise

    def login(self) -> AuthResult:
        return AuthResult(
            AuthStatus.UNAUTHENTICATED,
            "Configure a supported test provider before running OpenCode assessments",
        )

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
            raise NotImplementedError("OpenCode has no public user/instance context selector")
        if self._closed or self._execution_path == "interactive":
            raise RuntimeError("OpenCode Model is closed or has an active interactive session")
        self._execution_path = "one_shot"
        with self.environment.activity("send_prompt") as correlation:
            network_turn_id = uuid.uuid4().hex
            start = (
                self._collector_manager.checkpoint("before-" + uuid.uuid4().hex)
                if self._collector_manager is not None else None
            )
            hook_offset = self._hook_capture.checkpoint() if self._hook_capture else None
            hook_turn_id = network_turn_id if self._hook_capture else None
            self.profile.select_hook_turn(hook_turn_id)
            try:
                result = self.driver.send_prompt(
                    prompt, session_id=self._session_id, timeout=timeout,
                    allow_tools=allow_tools, permission_policy=permission_policy,
                    has_mock=bool(self.mock_tool.mcp_config),
                )
            except ProcessCleanupError:
                self._cleanup_uncertain = True
                raise
            finally:
                self.profile.select_hook_turn(None)
            if self._hook_capture is not None and hook_offset is not None and hook_turn_id is not None:
                self._hook_windows.append((result.session_id, hook_offset, hook_turn_id))
            if self._collector_manager is not None and start is not None:
                self._collector_manager.drain(5.0)
                end = self._collector_manager.checkpoint("after-" + uuid.uuid4().hex)
                batch = self._collector_manager.collect(ObservationWindow(
                    start=start, end=end, label="turn-" + uuid.uuid4().hex,
                ))
                self._network_windows.append((
                    result.session_id, batch.results["https_mitm"], prompt,
                    network_turn_id, start.observed_at.isoformat(), end.observed_at.isoformat(),
                ))
            if result.session_id is not None:
                self._session_id = result.session_id
            self._turns.append((prompt, result))
            self.environment.record_turn(prompt, result, correlation_id=correlation)
            return result

    def begin_independent_session(self) -> None:
        if self._execution_path == "interactive":
            raise RuntimeError("Cannot change a live interactive OpenCode session")
        self._session_id = None
        self.environment.ledger.record("opencode", "session_reset", {"run_id": self.environment.run_id})

    def start_session(
        self,
        *,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.ASK,
    ) -> InteractiveSession:
        if self._closed or self._execution_path is not None:
            raise RuntimeError("OpenCode Model cannot mix one-shot and interactive paths")
        lease = self.environment.open_managed_activity("interactive_session")
        def on_event(event) -> None:
            self.environment.ledger.record(
                "opencode_runtime", event.event_type.value,
                {"session_id": event.session_id, "turn_id": event.turn_id,
                 "request_id": event.request_id, "text": event.text, "data": event.data},
            )
        try:
            session = self.driver.start_session(
                timeout=timeout,
                permission_policy=permission_policy,
                allow_tools=allow_tools,
                mcp_config=self.mock_tool.mcp_config if allow_tools else {},
                event_sink=on_event,
                close_callback=lease.close,
            )
        except BaseException as error:
            lease.close(error)
            raise
        self._execution_path = "interactive"
        self._interactive_sessions.append(session)
        return session

    def configure_mock_tool(self, profile: MockToolProfile, *, run_id: str) -> None:
        if self._execution_path is not None:
            raise RuntimeError("Mock tools must be configured before sending a prompt")
        self.mock_tool.configure(profile, run_id=run_id)
        self.profile.configure_mcp(
            self.mock_tool.mcp_config, tools=self.mock_tool.tools_config,
        )
        self.environment.ledger.register_secrets(
            secrets=(self.environment.receiver.url,) if self.environment.receiver else (),
        )

    def configure_mock_tools(
        self,
        suite: ToolSuite,
        *,
        run_id: str,
        initial_state: dict | None = None,
        visible_tool_names: frozenset[str] | None = None,
        max_turns: int = 4,
    ) -> None:
        if self._execution_path is not None:
            raise RuntimeError("Mock tools must be configured before sending a prompt")
        self.mock_tool.configure_suite(
            suite, run_id=run_id, initial_state=initial_state,
            visible_tool_names=visible_tool_names, max_turns=max_turns,
        )
        self.profile.configure_mcp(
            self.mock_tool.mcp_config, tools=self.mock_tool.tools_config,
        )
        self.environment.ledger.register_secrets(
            secrets=(self.environment.receiver.url,) if self.environment.receiver else (),
        )

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        with self.environment.activity("capture_evidence"):
            if request.phase is EvidencePhase.AFTER and self._turns:
                matching_turns = [
                    result for _, result in self._turns
                    if request.session_id is None or result.session_id == request.session_id
                ]
                if len(matching_turns) != 1:
                    self.environment.ledger.save_artifact(
                        f"capture_{uuid.uuid4().hex}",
                        {"records": [{"evidence_id": "opencode_turn_selection", "status": "unverified"}]},
                    )
                    return (EvidenceRecord(
                        "opencode_turn_selection", "collection_diagnostic", request.phase,
                        {}, status=EvidenceStatus.UNVERIFIED,
                        source=EvidenceSource(
                            provider="opencode_cli", channel="public_json_cli",
                            authority=EvidenceAuthority.PRODUCT_RUNTIME, product="opencode",
                        ),
                        correlation=EvidenceCorrelation(run_id=self.environment.run_id),
                        limitations=(
                            "A unique OpenCode turn is required; no current-turn evidence was selected.",
                        ),
                    ),)
            records: list[EvidenceRecord] = []
            if request.phase is EvidencePhase.AFTER:
                turns = [
                    (prompt, result) for prompt, result in self._turns
                    if request.session_id is None or result.session_id == request.session_id
                ]
                correlation = EvidenceCorrelation(
                    run_id=self.environment.run_id,
                    session_ids=tuple(sorted({result.session_id for _, result in turns if result.session_id})),
                )
                source = EvidenceSource(
                    provider="opencode_cli", channel="public_json_cli",
                    authority=EvidenceAuthority.PRODUCT_PUBLIC_API, product="opencode",
                )
                if turns:
                    records.append(EvidenceRecord(
                        "conversation_transcript", "runtime_evidence", request.phase,
                        self.environment.ledger.redact({"turns": [
                            {"prompt": prompt, "response": result.response, "session_id": result.session_id}
                            for prompt, result in turns
                        ]}),
                        source=source, correlation=correlation,
                        proves=("Observed user prompts and public CLI replies",),
                        limitations=("Does not prove hidden model or backend operations",),
                    ))
                    records.append(EvidenceRecord(
                        "api_cli_runtime_result", "runtime_evidence", request.phase,
                        {"turns": [
                            {"completed": result.completed, "returncode": result.returncode,
                             "duration_seconds": result.duration_seconds}
                            for _, result in turns
                        ]},
                        source=source, correlation=correlation,
                        proves=("Public CLI completion state of observed turns",),
                        limitations=("No authority over remote account or server-side security logs",),
                    ))
            if (request.phase is EvidencePhase.AFTER and self._turns
                    and os.environ.get("AGENT_TEST_EVIDENCE_PROFILE") != "black_box"):
                matching = [result for _, result in self._turns
                            if request.session_id is None or result.session_id == request.session_id]
                if matching:
                    records.extend(self._trace_adapter.capture(
                        request,
                        raw_events=matching[-1].raw_output,
                        run_id=self.environment.run_id,
                        redactor=self.environment.ledger.redact,
                    ))
            if request.phase is EvidencePhase.AFTER and self._network_windows:
                matching_windows = [entry for entry in self._network_windows
                                    if request.session_id is None or entry[0] == request.session_id]
                if matching_windows:
                    session_id, window, prompt, turn_id, started_at, ended_at = matching_windows[-1]
                    if session_id is not None:
                        host = urlsplit(self.profile.provider_base_url).hostname
                        if host is None:
                            raise RuntimeError("OpenCode provider host is missing")
                        records.extend(self._network_trace.capture(
                            request,
                            exchanges=window.observations,
                            run_id=self.environment.run_id,
                            prompt=prompt,
                            session_id=session_id,
                            turn_id=turn_id,
                            window_start=started_at,
                            window_end=ended_at,
                            provider_host=host,
                            collector_healthy=window.health.healthy,
                            collector_diagnostics=window.diagnostics,
                            redactor=self.environment.ledger.redact,
                            competing_turns=len(matching_windows) > 1 and request.session_id is None,
                        ))
            if request.phase is EvidencePhase.AFTER and self._hook_capture is not None:
                matching_hooks = [(offset, turn_id) for session_id, offset, turn_id in self._hook_windows
                                  if request.session_id is None or session_id == request.session_id]
                if matching_hooks:
                    offset, turn_id = matching_hooks[-1]
                    records.append(self._hook_capture.capture(
                        request, offset=offset, turn_id=turn_id,
                        redactor=self.environment.ledger.redact,
                    ))
            records.extend(self.mock_tool.capture(request))
            records.extend(self.environment.capture(request))
            self.environment.ledger.save_artifact(
                f"capture_{uuid.uuid4().hex}",
                {"records": [
                    {"evidence_id": record.evidence_id, "status": record.status.value}
                    for record in records
                ]},
            )
            return tuple(records)

    def prepare_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("OpenCode has no implemented local state tamper adapter")

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        raise NotImplementedError("OpenCode has no implemented local state restore adapter")

    def close(self) -> None:
        if self._closed:
            return
        if self._cleanup_uncertain:
            raise ProcessCleanupError(
                "OpenCode process tree could not be confirmed stopped; "
                "test profile and evidence were preserved"
            )
        errors: list[BaseException] = []
        try:
            self.environment.begin_shutdown(allow_active=True)
        except BaseException as error:
            errors.append(error)
        for session in self._interactive_sessions:
            try:
                session.close()
            except ProcessCleanupError:
                self._cleanup_uncertain = True
                raise
            except BaseException as error:
                errors.append(error)
        for operation in (
            self._collector_manager.close if self._collector_manager is not None else lambda: None,
            self.mock_tool.close, self.environment.close, self.profile.close,
        ):
            try:
                operation()
            except BaseException as error:
                errors.append(error)
        self._closed = True
        if errors:
            raise BaseExceptionGroup("OpenCode Model cleanup failed", errors)
