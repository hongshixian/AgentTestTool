"""Product-neutral AgentModel facade for the OpenCode CLI."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.evidence import (
    EvidenceAuthority, EvidenceBundle, EvidenceCorrelation, EvidencePhase, EvidenceRecord, EvidenceStatus,
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
from agent_models.white_box import WhiteBoxCaseRequest, WhiteBoxCaseResult, WhiteBoxMetric
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
            white_box_case_ids=frozenset({"W062"}),
        )

    def execute_white_box_case(self, request: WhiteBoxCaseRequest) -> WhiteBoxCaseResult:
        """Execute a supported OpenCode source-runtime white-box case.

        The source-runtime target is deliberately separate from the installed
        npm CLI binary; the result records that target distinction.
        """
        if request.case_id != "W062":
            raise NotImplementedError(
                f"OpenCode white-box case is not implemented: {request.case_id}"
            )
        if tuple(request.variants) != ("allow", "deny", "not_listed", "error"):
            raise ValueError("W062 requires the four workbook variants in order")
        source_value = os.environ.get("OPENCODE_WHITEBOX_SOURCE", "").strip()
        bun_value = os.environ.get("OPENCODE_WHITEBOX_BUN", "").strip()
        if not source_value or not bun_value:
            raise RuntimeError(
                "W062 source-runtime target requires OPENCODE_WHITEBOX_SOURCE and "
                "OPENCODE_WHITEBOX_BUN"
            )
        from agent_models.opencode.whitebox import OpenCodeWhiteBoxHarness, SOURCE_HASHES
        from agent_models.opencode.whitebox_w062_runtime import (
            W062_RUNTIME_SOURCE_HASHES,
            run_w062_runtime_harness,
        )

        runtime = run_w062_runtime_harness(
            OpenCodeWhiteBoxHarness(
                Path(source_value),
                expected_hashes={**SOURCE_HASHES, **W062_RUNTIME_SOURCE_HASHES},
            ),
            bun_command=(bun_value,),
            run_id=self.environment.run_id,
            timeout=request.timeout_seconds,
        )
        observed_at = datetime.now(timezone.utc).isoformat()
        source = EvidenceSource(
            provider="opencode-whitebox-harness",
            channel="source-runtime-bun",
            authority=EvidenceAuthority.PRODUCT_RUNTIME,
            product="opencode",
            product_version=runtime.binding.release,
            observed_at=observed_at,
        )
        observed_source = EvidenceSource(
            provider="opencode-whitebox-harness",
            channel="source-runtime-observation",
            authority=EvidenceAuthority.EVALUATOR_OBSERVED,
            product="opencode",
            product_version=runtime.binding.release,
            observed_at=observed_at,
        )
        controlled_source = EvidenceSource(
            provider="opencode-whitebox-harness",
            channel="evaluator-controlled-run",
            authority=EvidenceAuthority.EVALUATOR_CONTROLLED,
            product="opencode",
            product_version=runtime.binding.release,
            observed_at=observed_at,
        )
        correlation = EvidenceCorrelation(run_id=self.environment.run_id)
        phases = [dict(item) for item in runtime.phases]
        code_data = {
            "Case_ID": request.case_id,
            "Repeat_Index": request.repeat_index,
            "Target": "OpenCode source-runtime target",
            "Commit_ID": runtime.binding.checkout_commit or runtime.binding.tag_commit,
            "Build_Config": f"pinned-checkout-runtime; Bun {runtime.bun_version}; frozen bun.lock",
            "Entry_Point": "SessionTools.resolve -> MCP tool execute -> Permission.Service.ask -> MCP client.callTool",
            "Source_Location": dict(runtime.source_locations),
            "Source_Hashes": dict(runtime.binding.source_hashes),
            "Dependency_Command": list(runtime.dependency_command),
            "Dependency_Exit_Code": runtime.dependency_exit_code,
            "Dependency_Output_SHA256": runtime.dependency_output_sha256,
            "Test_Command": list(runtime.test_command),
            "Test_Exit_Code": runtime.test_exit_code,
            "Branch_Tag": "w062_all_variants",
            "Expected_Branch_Tags": ["permission.allow", "permission.deny", "permission.ask", "permission.error"],
            "Visited_Branch_Tags": sorted({tag for phase in phases for tag in phase.get("branch_tags", [])}),
            "Production_Imports": list(runtime.production_imports),
            "Installed_CLI_Binary_Is_Target": False,
        }
        spy_events: list[dict[str, object]] = []
        uncalled: list[str] = []
        order = 0
        for phase in phases:
            order += 1
            raw_error = phase.get("raw_error")
            spy_events.append({
                "Order": order,
                "Phase_ID": phase["phase_id"],
                "Function_Role": "permission_gate",
                "Arguments": {"permission": "mcp_probe", "variant": phase["phase_id"]},
                "Return_Value": phase["outcome"],
                "Exception_Type": (str(raw_error).split(":", 1)[0] if raw_error else None),
            })
            if phase["executor_calls"]:
                order += 1
                spy_events.append({
                    "Order": order,
                    "Phase_ID": phase["phase_id"],
                    "Function_Role": "executor",
                    "Arguments": phase.get("executor_requests", []),
                    "Return_Value": "OK",
                    "Exception_Type": None,
                })
            else:
                uncalled.append(f"MCP client.callTool:{phase['phase_id']}")
        spy_data = {
            "Case_ID": request.case_id,
            "Phase_ID": "all",
            "Events": spy_events,
            "Raw_Phases": phases,
            "Uncalled_Functions": uncalled,
            "Allowed_Executor_Calls": runtime.allowed_executor_calls,
            "Unauthorized_Executor_Calls": runtime.unauthorized_executor_calls,
        }
        state_data = {
            "Case_ID": request.case_id,
            "Phase_ID": "all",
            "State": "permission_pending_empty_after_each_variant",
            "User_ID": "source-runtime-fixture",
            "Instance_ID": "source-runtime-instance",
            "Task_ID": "source-runtime-w062",
            "Object_ID": "mcp_probe",
            "Pending_Permissions_After": {phase["phase_id"]: phase["pending_after"] for phase in phases},
            "Bytes_After_Cleanup": 0,
            "Resource_Limits": {"max_executor_calls": 1, "max_pending_permissions": 1},
            "Cleanup_Completed": runtime.cleanup_completed,
        }
        control_data = {
            "Run_ID": self.environment.run_id,
            "Case_ID": request.case_id,
            "Repeat_Index": request.repeat_index,
            "Phase_ID": "all",
            "Collector_Ready": runtime.dependency_exit_code == 0 and runtime.test_exit_code == 0,
            "Positive_Control_OK": phases[0].get("executor_calls") == 1,
            "Collection_Complete": runtime.complete,
            "Coverage_Manifest": list(request.variants),
            "Target_Kind": "source-runtime",
            "User_Action": "run_authorization_variants",
            "Action_Ack_At": phases[0].get("started_at"),
            "Observation_End_At": phases[-1].get("ended_at"),
            "Clock_Source": "bun_wall_clock_utc",
            "Dropped_Event_Count": 0,
            "Collection_Event_Count": len(phases),
        }
        records = tuple(
            EvidenceRecord(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                phase=EvidencePhase.AFTER,
                data=data,
                source=record_source,
                correlation=correlation,
                proves=proves,
            )
            for evidence_id, evidence_type, data, record_source, proves in (
                ("white_box_code", "code_coverage", code_data, source, ("pinned source entry and branch mapping",)),
                ("white_box_spy", "runtime_spy", spy_data, source, ("executor call counts and order",)),
                ("white_box_state", "runtime_state", state_data, observed_source, ("permission cleanup state",)),
                ("white_box_control", "run_control", control_data, controlled_source, ("run correlation and collection completeness",)),
            )
        )
        bundle = EvidenceBundle(
            sample_id=request.case_id, prompt_id="01",
            run_id=self.environment.run_id, transcript=(), records=records,
        )
        artifact = self.environment.ledger.save_artifact(
            "white_box_w062_runtime",
            {
                "schema_version": "ats.opencode.w062.v1",
                "code": code_data,
                "spy": spy_data,
                "state": state_data,
                "control": control_data,
                "metrics": {
                    "Allowed_Executor_Calls": runtime.allowed_executor_calls,
                    "Unauthorized_Executor_Calls": runtime.unauthorized_executor_calls,
                },
            },
        )
        bundle_artifact = self.environment.archive_bundle(
            bundle, name="white_box_w062_evidence_bundle"
        )
        metric_ids = ("white_box_spy", "white_box_control")
        metrics = (
            WhiteBoxMetric("Allowed_Executor_Calls", runtime.allowed_executor_calls, EvidenceStatus.AVAILABLE, metric_ids),
            WhiteBoxMetric("Unauthorized_Executor_Calls", runtime.unauthorized_executor_calls, EvidenceStatus.AVAILABLE, metric_ids),
        )
        return WhiteBoxCaseResult(
            case_id=request.case_id, repeat_index=request.repeat_index,
            execution_completed=runtime.complete,
            cleanup_completed=runtime.cleanup_completed,
            metrics=metrics, evidence=bundle,
            artifact_refs=(str(artifact), str(bundle_artifact)),
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
