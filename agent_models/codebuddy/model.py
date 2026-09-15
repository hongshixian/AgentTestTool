"""CodeBuddy implementation of the public Agent Model facade."""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agent_models.base import AgentModel
from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.driver import CodeBuddyDriver
from agent_models.codebuddy.evidence import (
    CodeBuddyCommandEvidenceProvider,
    CodeBuddyStreamEvidenceAdapter,
)
from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController
from agent_models.codebuddy.memory import CodeBuddyMemoryStateController
from agent_models.codebuddy.mock_tool import CodeBuddyMockToolController
from agent_models.codebuddy.trace_adapter import (
    CodeBuddyTraceAdapter,
    TraceTurnIdentity,
    TraceTurnObservation,
)
from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceCorrelation,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    EvidenceStatus,
    JsonValue,
    RequestContext,
)
from agent_models.environment.session import ControlledEnvironment
from agent_models.interaction import (
    AgentEvent,
    AgentEventType,
    BackgroundTaskControlResult,
    BackgroundTaskHandle,
    BackgroundTaskObservation,
    InteractiveSession,
    PermissionPolicy,
)
from agent_models.local_state import LocalStateAction, LocalStateRequest
from agent_models.memory import MemoryStateRequest
from agent_models.result import AuthResult, InstallationResult, TurnResult
from agent_models.tools import MockToolProfile, ToolSuite
from evidence_collectors.atif import AtifConverter
from evidence_collectors.base import (
    CollectionCheckpoint,
    CollectorHealthState,
    CollectorStatus,
    ObservationWindow,
)
from evidence_collectors.manager import EvidenceCollectorManager
from evidence_collectors.trace import AgentTrace, TraceReadyState


_BACKGROUND_TERMINAL_STATES = frozenset(
    {"done", "failed", "cancelled", "canceled", "stopped", "killed"}
)


@dataclass(frozen=True, slots=True)
class _TraceWindowStart:
    turn_id: str
    prompt: str
    session_id: str
    checkpoint: CollectionCheckpoint
    started_at: str
    task_id: str | None = None


@dataclass(frozen=True, slots=True)
class _TraceCollectorQuality:
    health_state: CollectorHealthState = CollectorHealthState.HEALTHY
    lost_records: int = 0
    limitations: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    failed: bool = False


@dataclass(slots=True)
class _TraceWindowFinalization:
    observation: TraceTurnObservation
    quality: _TraceCollectorQuality
    result_status: str
    result_health: str
    failure_detail: str | None
    artifact_references: list[dict[str, JsonValue]] = field(default_factory=list)
    artifacts_complete: bool = False
    capture_event_recorded: bool = False


def _trace_intervals_overlap(
    first_start: str | None,
    first_end: str | None,
    second_start: str | None,
    second_end: str | None,
) -> bool:
    """Treat malformed or open intervals as overlapping so attribution fails closed."""

    def parse(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed

    start_a = parse(first_start)
    end_a = parse(first_end)
    start_b = parse(second_start)
    end_b = parse(second_end)
    if start_a is None or end_a is None or start_b is None:
        return True
    return start_a <= (end_b or end_a) and start_b <= end_a


class CodeBuddyAgentModel(AgentModel):
    def __init__(
        self,
        *,
        workspace: Path,
        driver: CodeBuddyDriver,
        evidence: CodeBuddyCommandEvidenceProvider,
        mock_tool: CodeBuddyMockToolController,
        local_state: CodeBuddyCommandLocalStateController,
        memory_state: CodeBuddyMemoryStateController | None = None,
        environment: ControlledEnvironment | None = None,
        collector_manager: EvidenceCollectorManager | None = None,
        test_case_id: str | None = None,
    ) -> None:
        self._workspace = workspace
        self.driver = driver
        self.evidence = evidence
        self.mock_tool = mock_tool
        self.local_state = local_state
        self.memory_state = memory_state
        self._session_id = f"ats-{uuid.uuid4().hex}"
        self._has_started_session = False
        self._has_attempted_session = False
        self._execution_path: str | None = None
        self._environment = environment
        self._closed = False
        self._interactive_events: list[AgentEvent] = []
        self._interactive_events_lock = threading.RLock()
        self._stream_evidence = CodeBuddyStreamEvidenceAdapter()
        self._memory_records: list[EvidenceRecord] = []
        self._collector_manager = collector_manager
        self._test_case_id = test_case_id
        self._trace_adapter = CodeBuddyTraceAdapter()
        self._atif_converter = AtifConverter()
        self._trace_turns: list[TraceTurnObservation] = []
        self._trace_lock = threading.RLock()
        self._interactive_trace_windows: dict[str, _TraceWindowStart] = {}
        self._background_trace_windows: dict[str, _TraceWindowStart] = {}
        self._finalized_trace_window_ids: set[str] = set()
        self._trace_finalizations: dict[str, _TraceWindowFinalization] = {}
        self._trace_quality_by_turn: dict[str, _TraceCollectorQuality] = {}
        self._collector_health_state = CollectorHealthState.HEALTHY
        self._collector_lost_records = 0
        self._collector_limitations: list[str] = []
        self._collector_errors: list[str] = []
        self._unscoped_collector_errors: list[str] = []
        self._network_artifacts: list[dict[str, JsonValue]] = []

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
        memory_state_available = (
            self.memory_state is not None and self.memory_state.is_available()
        )
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
            interactive_session=True,
            streaming_events=True,
            runtime_control=True,
            permission_control=True,
            background_task_events=True,
            independent_sessions=True,
            background_tasks=True,
            background_task_control=True,
            background_task_inventory_evidence=True,
            background_task_log_evidence=True,
            product_runtime_evidence=True,
            session_correlation_evidence=True,
            tool_event_evidence=True,
            permission_event_evidence=True,
            task_event_evidence=True,
            network_traffic_evidence=self._collector_manager is not None,
            reconstructed_agent_trace=self._collector_manager is not None,
            persistent_memory_state=True,
            persistent_memory_state_control=memory_state_available,
        )

    def check_authentication(self) -> AuthResult:
        with self.environment.activity("authentication") as correlation:
            result = self._check_authentication()
            self.environment.ledger.record("agent_model", "authentication", asdict(result), correlation)
            return result

    def check_installation(self) -> InstallationResult:
        with self.environment.activity("installation") as correlation:
            result = self.driver.check_installation()
            self.environment.ledger.record(
                "agent_model",
                "installation",
                asdict(result),
                correlation,
            )
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
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
    ) -> TurnResult:
        if context is not None:
            raise RuntimeError("CodeBuddy CLI 未公开用户或实例身份上下文选择参数")
        if self._execution_path == "interactive":
            raise RuntimeError("一个 Agent Model 不能混用单轮与长驻会话执行路径")
        self._execution_path = "one_shot"
        with self.environment.activity("send_prompt") as correlation:
            self._has_attempted_session = True
            trace_window = self._begin_trace_window(
                prompt=prompt,
                turn_id=f"turn-{uuid.uuid4().hex}",
                session_id=self._session_id,
            )
            self.environment.ledger.record("agent_model", "prompt",
                                            {"prompt": prompt, "session_id": self._session_id,
                                            "allow_tools": allow_tools,
                                            "permission_policy": permission_policy.value}, correlation)
            try:
                turn = self.driver.send_prompt(
                    prompt, timeout=timeout, session_id=self._session_id,
                    resume=self._has_started_session, allow_tools=allow_tools,
                    permission_policy=permission_policy,
                    extra_args=self.mock_tool.extra_args if allow_tools else (),
                )
            except subprocess.TimeoutExpired as error:
                def decode(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
                self.environment.ledger.record("agent_model", "turn_timeout",
                    {"stdout": decode(error.stdout), "stderr": decode(error.stderr)}, correlation)
                try:
                    self._finish_trace_window(trace_window)
                except BaseException as collector_error:
                    raise BaseExceptionGroup(
                        "CodeBuddy timeout and network evidence collection both failed",
                        [error, collector_error],
                    ) from None
                raise
            except BaseException as primary_error:
                try:
                    self._finish_trace_window(trace_window)
                except BaseException as collector_error:
                    raise BaseExceptionGroup(
                        "CodeBuddy turn and network evidence collection both failed",
                        [primary_error, collector_error],
                    ) from None
                raise
            else:
                self._finish_trace_window(trace_window)
            self.environment.record_turn(prompt, turn, correlation_id=correlation)
            if turn.completed:
                self._has_started_session = True
            return turn

    def start_session(
        self,
        *,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.ASK,
    ) -> InteractiveSession:
        if self._execution_path == "one_shot":
            raise RuntimeError("一个 Agent Model 不能混用单轮与长驻会话执行路径")
        if self.driver.interactive_sessions:
            raise RuntimeError("必须先关闭当前长驻会话，再启动新的独立会话")
        self._execution_path = "interactive"
        lease = self.environment.open_managed_activity("interactive_session")
        self._has_attempted_session = True
        interactive_session_id = f"ats-{uuid.uuid4().hex}"

        def record_event(event: AgentEvent) -> None:
            with self._interactive_events_lock:
                self._interactive_events.append(event)
            self.environment.ledger.record(
                "codebuddy_cli",
                "interactive_event",
                asdict(event),
                lease.correlation_id,
            )
            if event.event_type is AgentEventType.USER_INPUT and event.turn_id:
                try:
                    window = self._begin_trace_window(
                        prompt=event.text,
                        turn_id=event.turn_id,
                        session_id=event.session_id or interactive_session_id,
                    )
                    with self._trace_lock:
                        self._interactive_trace_windows[event.turn_id] = window
                except BaseException as error:
                    self._record_collector_failure("interactive checkpoint", error)
            elif event.event_type is AgentEventType.TURN_COMPLETED and event.turn_id:
                with self._trace_lock:
                    window = self._interactive_trace_windows.get(event.turn_id)
                if window is not None:
                    try:
                        self._finish_trace_window(
                            window,
                            completed_at=event.observed_at,
                            stream_events=self._events_for_turn(event.turn_id),
                        )
                    except BaseException as error:
                        with self._trace_lock:
                            finalized = (
                                window.turn_id in self._finalized_trace_window_ids
                            )
                        if not finalized:
                            self._record_collector_failure(
                                "interactive collection", error
                            )
                    finally:
                        with self._trace_lock:
                            if (
                                window.turn_id in self._finalized_trace_window_ids
                                and self._interactive_trace_windows.get(event.turn_id)
                                is window
                            ):
                                self._interactive_trace_windows.pop(event.turn_id)

        try:
            session = self.driver.start_session(
                session_id=interactive_session_id,
                timeout=timeout,
                allow_tools=allow_tools,
                permission_policy=permission_policy,
                extra_args=self.mock_tool.extra_args if allow_tools else (),
                event_sink=record_event,
                close_callback=lease.close,
            )
        except BaseException as error:
            lease.close(error)
            raise
        return session

    def start_background_task(
        self,
        prompt: str,
        *,
        name: str,
        timeout: float | None = None,
        allow_tools: bool = True,
        permission_policy: PermissionPolicy = PermissionPolicy.DENY_UNAPPROVED,
    ) -> BackgroundTaskHandle:
        if self._execution_path in {"one_shot", "interactive"}:
            raise RuntimeError("一个 Agent Model 不能混用后台任务与其他会话执行路径")
        self._execution_path = "background"
        self._has_attempted_session = True
        with self.environment.activity("start_background_task") as correlation:
            trace_window = self._begin_trace_window(
                prompt=prompt,
                turn_id=f"background-{uuid.uuid4().hex}",
                session_id=self._session_id,
            )
            try:
                handle = self.driver.start_background_task(
                    prompt,
                    name=name,
                    timeout=timeout,
                    allow_tools=allow_tools,
                    permission_policy=permission_policy,
                    extra_args=self.mock_tool.extra_args if allow_tools else (),
                )
            except BaseException as primary_error:
                try:
                    self._finish_trace_window(trace_window)
                except BaseException as collector_error:
                    raise BaseExceptionGroup(
                        "CodeBuddy background launch and evidence collection both failed",
                        [primary_error, collector_error],
                    ) from None
                raise
            if trace_window is not None:
                with self._trace_lock:
                    self._background_trace_windows[handle.task_id] = _TraceWindowStart(
                        turn_id=trace_window.turn_id,
                        prompt=trace_window.prompt,
                        session_id=handle.session_id or trace_window.session_id,
                        checkpoint=trace_window.checkpoint,
                        started_at=trace_window.started_at,
                        task_id=handle.task_id,
                    )
            self.environment.ledger.record(
                "codebuddy_cli",
                "background_task_started",
                asdict(handle),
                correlation,
            )
            return handle

    def observe_background_tasks(self) -> tuple[BackgroundTaskObservation, ...]:
        with self.environment.activity("observe_background_tasks") as correlation:
            observations = self.driver.observe_background_tasks()
            self.environment.ledger.record(
                "codebuddy_cli",
                "background_task_inventory",
                {"tasks": [asdict(item) for item in observations]},
                correlation,
            )
            return observations

    def read_background_task_logs(self, task_id: str) -> str:
        with self.environment.activity("read_background_task_logs") as correlation:
            logs = self.driver.read_background_task_logs(task_id)
            self.environment.ledger.record(
                "codebuddy_cli",
                "background_task_logs",
                {"task_id": task_id, "logs": logs},
                correlation,
            )
            return logs

    def stop_background_task(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> BackgroundTaskControlResult:
        with self.environment.activity("stop_background_task") as correlation:
            result = self.driver.stop_background_task(task_id, timeout=timeout)
            self.environment.ledger.record(
                "codebuddy_cli",
                "background_task_control",
                asdict(result),
                correlation,
            )
            return result

    def capture_evidence(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        with self.environment.activity("capture_evidence"):
            self._finish_background_trace_if_pending(request.task_id)
            external_records = self.evidence.capture(request) if self.evidence.is_available() else ()
            with self._interactive_events_lock:
                interactive_events = tuple(self._interactive_events)
            stream_records = (
                self._stream_evidence.capture(
                    request,
                    events=interactive_events,
                    run_id=self.environment.run_id,
                )
                if interactive_events
                else ()
            )
            background_records = (
                self._capture_background_task_evidence(request)
                if request.task_id is not None
                else ()
            )
            mock_tool_records = self.mock_tool.capture(request)
            trace_records = self._capture_trace_evidence(
                request,
                tool_records=mock_tool_records,
            )
            records = (
                external_records
                + stream_records
                + background_records
                + mock_tool_records
                + trace_records
                + self.environment.capture(request)
                + tuple(self._memory_records)
            )
            self.environment.ledger.save_artifact(
                f"capture_{uuid.uuid4().hex}",
                {
                    "records": [
                        {
                            "evidence_id": record.evidence_id,
                            "type": record.evidence_type,
                            "phase": record.phase.value,
                            "status": record.status.value,
                            "correlation": record.correlation.judge_payload(),
                        }
                        for record in records
                    ],
                    "network_artifacts": [
                        dict(item) for item in self._network_artifacts
                    ],
                    "scope": (
                        "Capture manifest only; bounded evidence payloads are "
                        "stored in referenced artifacts."
                    ),
                },
            )
            return records

    def _capture_background_task_evidence(
        self,
        request: EvidenceRequest,
    ) -> tuple[EvidenceRecord, ...]:
        task_id = request.task_id
        if task_id is None:
            return ()
        observed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        source = EvidenceSource(
            provider="codebuddy_cli",
            channel="agents_jobs",
            authority=EvidenceAuthority.PRODUCT_RUNTIME,
            product="codebuddy",
            observed_at=observed_at,
        )
        observations = self.driver.observe_background_tasks()
        observation = next(
            (item for item in observations if item.task_id == task_id),
            None,
        )
        correlation = EvidenceCorrelation(
            run_id=self.environment.run_id,
            session_ids=(
                (observation.session_id,)
                if observation is not None and observation.session_id
                else ()
            ),
            task_ids=(task_id,),
        )
        inventory = EvidenceRecord(
            evidence_id="agent_background_task_state",
            evidence_type="runtime_evidence",
            phase=request.phase,
            data=asdict(observation) if observation is not None else {},
            status=(
                EvidenceStatus.AVAILABLE
                if observation is not None
                else EvidenceStatus.MISSING
            ),
            source=source,
            correlation=correlation,
            proves=("CodeBuddy 公开后台任务清单在采集时报告的任务和状态",),
            limitations=(
                "本地产品运行时清单不证明云端任务状态、账号身份或安全审计事实。",
            ),
        )
        try:
            logs = self.driver.read_background_task_logs(task_id)
        except RuntimeError:
            log_record = EvidenceRecord(
                evidence_id="agent_background_task_log",
                evidence_type="runtime_evidence",
                phase=request.phase,
                data={},
                status=EvidenceStatus.ERROR,
                source=EvidenceSource(
                    provider="codebuddy_cli",
                    channel="logs",
                    authority=EvidenceAuthority.PRODUCT_RUNTIME,
                    product="codebuddy",
                    observed_at=observed_at,
                ),
                correlation=correlation,
                proves=("CodeBuddy 公开日志命令返回的后台任务运行文本",),
                limitations=("日志命令失败，当前记录不能证明任务过程。",),
            )
        else:
            log_record = EvidenceRecord(
                evidence_id="agent_background_task_log",
                evidence_type="runtime_evidence",
                phase=request.phase,
                data={"logs": logs},
                source=EvidenceSource(
                    provider="codebuddy_cli",
                    channel="logs",
                    authority=EvidenceAuthority.PRODUCT_RUNTIME,
                    product="codebuddy",
                    observed_at=observed_at,
                ),
                correlation=correlation,
                proves=("CodeBuddy 公开日志命令返回的后台任务运行文本",),
                limitations=(
                    "运行日志不等于服务端安全审计日志，也不证明未记录通道没有执行。",
                ),
            )
        return inventory, log_record

    def _begin_trace_window(
        self,
        *,
        prompt: str,
        turn_id: str,
        session_id: str,
    ) -> _TraceWindowStart | None:
        manager = self._collector_manager
        if manager is None:
            return None
        checkpoint = manager.checkpoint(f"{turn_id}-before")
        return _TraceWindowStart(
            turn_id=turn_id,
            prompt=prompt,
            session_id=session_id,
            checkpoint=checkpoint,
            started_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        )

    def _finish_trace_window(
        self,
        window: _TraceWindowStart | None,
        *,
        completed_at: str | None = None,
        stream_events: tuple[AgentEvent, ...] = (),
    ) -> None:
        manager = self._collector_manager
        if manager is None or window is None:
            return
        with self._trace_lock:
            if window.turn_id in self._finalized_trace_window_ids:
                return
            finalization = self._trace_finalizations.get(window.turn_id)
            if finalization is None:
                drained = manager.drain(10.0)
                after = manager.checkpoint(f"{window.turn_id}-after")
                batch = manager.collect(
                    ObservationWindow(window.checkpoint, after, window.turn_id)
                )
                result = batch.results["https_mitm"]
                drain_result = drained.results["https_mitm"]
                result_quality = self._assess_trace_collector_quality(result)
                drain_quality = _TraceCollectorQuality()
                if drain_result.status is CollectorStatus.TIMEOUT:
                    drain_quality = self._quality_from_collector_result(
                        drain_result
                    )
                window_quality = self._combine_trace_quality(
                    result_quality,
                    drain_quality,
                )
                exchanges = tuple(
                    record
                    for record in result.observations
                    if isinstance(record, dict)
                )
                finished_at = completed_at or datetime.now(timezone.utc).isoformat(
                    timespec="milliseconds"
                )
                failure_detail = None
                if window_quality.failed:
                    failure_detail = (
                        drain_result.health.detail
                        if drain_result.status is CollectorStatus.TIMEOUT
                        else result.health.detail or result.status.value
                    )
                finalization = _TraceWindowFinalization(
                    observation=TraceTurnObservation(
                        turn_id=window.turn_id,
                        prompt=window.prompt,
                        session_id=window.session_id,
                        exchanges=exchanges,
                        started_at=window.started_at,
                        completed_at=finished_at,
                        stream_events=stream_events,
                        task_id=window.task_id,
                        competing_turns=self._competing_trace_turns(
                            window,
                            completed_at=finished_at,
                        ),
                    ),
                    quality=window_quality,
                    result_status=result.status.value,
                    result_health=result.health.state.value,
                    failure_detail=failure_detail,
                )
                self._trace_finalizations[window.turn_id] = finalization

            if not finalization.artifacts_complete:
                self._archive_network_turn(
                    window,
                    finalization.observation.exchanges,
                    references=finalization.artifact_references,
                )
                finalization.artifacts_complete = True
            if not finalization.capture_event_recorded:
                if not self._trace_capture_event_exists(window.turn_id):
                    self.environment.ledger.record(
                        "network_collector",
                        "turn_captured",
                        {
                            "turn_id": window.turn_id,
                            "session_id": window.session_id,
                            "exchange_count": len(
                                finalization.observation.exchanges
                            ),
                            "status": finalization.result_status,
                            "health": finalization.result_health,
                        },
                        window.turn_id,
                    )
                finalization.capture_event_recorded = True

            self._trace_turns.append(finalization.observation)
            self._trace_quality_by_turn[window.turn_id] = finalization.quality
            self._merge_collector_quality(finalization.quality)
            self._network_artifacts.extend(finalization.artifact_references)
            self._finalized_trace_window_ids.add(window.turn_id)
            self._trace_finalizations.pop(window.turn_id, None)
            if finalization.quality.failed:
                raise RuntimeError(
                    "CodeBuddy 网络证据采集失败："
                    + (finalization.failure_detail or finalization.result_status)
                )

    def _trace_capture_event_exists(self, turn_id: str) -> bool:
        return any(
            event.get("source") == "network_collector"
            and event.get("kind") == "turn_captured"
            and event.get("correlation_id") == turn_id
            for event in self.environment.ledger.events
        )

    def _update_trace_collector_quality(self, result) -> bool:
        """Keep network-wide failures separate from model Trace completeness."""

        quality = self._assess_trace_collector_quality(result)
        self._merge_collector_quality(quality)
        return quality.failed

    def _assess_trace_collector_quality(self, result) -> _TraceCollectorQuality:
        """Assess only the model-relevant quality of one observation window."""

        observations = tuple(
            item for item in result.observations if isinstance(item, Mapping)
        )
        model_exchanges = tuple(
            item
            for item in observations
            if str(item.get("method", "")).upper() == "POST"
            and str(item.get("path", "")).split("?", 1)[0]
            == "/v2/chat/completions"
        )

        def incomplete(item: Mapping[str, object]) -> bool:
            return bool(
                item.get("error")
                or item.get("request_complete") is False
                or item.get("response_complete") is False
                or item.get("request_body_truncated") is True
                or item.get("response_body_truncated") is True
            )

        model_failures = tuple(item for item in model_exchanges if incomplete(item))
        unrelated_failures = tuple(
            item
            for item in observations
            if item not in model_exchanges and incomplete(item)
        )
        diagnostics_complete = {
            "resource_limits",
            "unattributed_error_count",
        }.issubset(result.diagnostics)
        resource_limits = result.diagnostics.get("resource_limits", [])
        unattributed_errors = result.diagnostics.get("unattributed_error_count", 0)
        unsafe_global_failure = (
            (
                result.status in {CollectorStatus.ERROR, CollectorStatus.UNVERIFIED}
                and not diagnostics_complete
            )
            or bool(resource_limits)
            or not isinstance(unattributed_errors, int)
            or isinstance(unattributed_errors, bool)
            or unattributed_errors > 0
        )
        if model_failures or unsafe_global_failure:
            return self._quality_from_collector_result(result)
        if result.status in {CollectorStatus.ERROR, CollectorStatus.UNVERIFIED}:
            if unrelated_failures:
                return _TraceCollectorQuality(
                    limitations=(
                        "非模型配置、遥测或报告交换存在异常；该异常保留在整体网络证据中，"
                        "但未影响已完整观察的模型请求与响应。",
                    )
                )
            # Collectors without scoped diagnostics cannot prove that an
            # unhealthy result was unrelated to the model channel.
            return self._quality_from_collector_result(result)
        return self._quality_from_collector_result(result)

    @staticmethod
    def _quality_from_collector_result(result) -> _TraceCollectorQuality:
        health_state = result.health.state
        if result.status in {CollectorStatus.ERROR, CollectorStatus.TIMEOUT}:
            health_state = CollectorHealthState.UNHEALTHY
        elif (
            result.status is CollectorStatus.UNVERIFIED
            and health_state is CollectorHealthState.HEALTHY
        ):
            health_state = CollectorHealthState.DEGRADED
        errors = (
            (result.health.detail or f"collector status: {result.status.value}",)
            if health_state is CollectorHealthState.UNHEALTHY
            else ()
        )
        limitations = tuple(result.limitations)
        if result.health.detail and not errors:
            limitations = (*limitations, result.health.detail)
        return _TraceCollectorQuality(
            health_state=health_state,
            lost_records=result.health.lost_record_count,
            limitations=limitations,
            errors=errors,
            failed=result.status
            in {CollectorStatus.ERROR, CollectorStatus.TIMEOUT},
        )

    @staticmethod
    def _combine_trace_quality(
        *qualities: _TraceCollectorQuality,
    ) -> _TraceCollectorQuality:
        state = CollectorHealthState.HEALTHY
        lost_records = 0
        limitations: list[str] = []
        errors: list[str] = []
        failed = False
        for quality in qualities:
            if quality.health_state is CollectorHealthState.UNHEALTHY:
                state = CollectorHealthState.UNHEALTHY
            elif (
                quality.health_state is CollectorHealthState.DEGRADED
                and state is CollectorHealthState.HEALTHY
            ):
                state = CollectorHealthState.DEGRADED
            lost_records += quality.lost_records
            limitations.extend(quality.limitations)
            errors.extend(quality.errors)
            failed = failed or quality.failed
        return _TraceCollectorQuality(
            health_state=state,
            lost_records=lost_records,
            limitations=tuple(dict.fromkeys(limitations)),
            errors=tuple(dict.fromkeys(errors)),
            failed=failed,
        )

    def _merge_collector_quality(self, quality: _TraceCollectorQuality) -> None:
        if quality.health_state is CollectorHealthState.UNHEALTHY:
            self._collector_health_state = CollectorHealthState.UNHEALTHY
        elif (
            quality.health_state is CollectorHealthState.DEGRADED
            and self._collector_health_state is CollectorHealthState.HEALTHY
        ):
            self._collector_health_state = CollectorHealthState.DEGRADED
        self._collector_lost_records += quality.lost_records
        self._collector_limitations.extend(quality.limitations)
        self._collector_errors.extend(quality.errors)

    def _finish_background_trace_if_pending(self, task_id: str | None) -> None:
        with self._trace_lock:
            if not self._background_trace_windows:
                return
        observations = {
            item.task_id: item for item in self.driver.observe_background_tasks()
        }
        with self._trace_lock:
            if task_id is None:
                selected = tuple(
                    (candidate_id, self._background_trace_windows[candidate_id])
                    for candidate_id in self._background_trace_windows
                    if (
                        candidate_id in observations
                        and observations[candidate_id].state.casefold()
                        in _BACKGROUND_TERMINAL_STATES
                    )
                )
            else:
                observation = observations.get(task_id)
                selected = (
                    ((task_id, self._background_trace_windows[task_id]),)
                    if observation is not None
                    and observation.state.casefold() in _BACKGROUND_TERMINAL_STATES
                    and task_id in self._background_trace_windows
                    else ()
                )
            for candidate_id, window in selected:
                try:
                    self._finish_trace_window(window)
                finally:
                    if (
                        window.turn_id in self._finalized_trace_window_ids
                        and self._background_trace_windows.get(candidate_id) is window
                    ):
                        self._background_trace_windows.pop(candidate_id)

    def _competing_trace_turns(
        self,
        window: _TraceWindowStart,
        *,
        completed_at: str,
    ) -> tuple[TraceTurnIdentity, ...]:
        candidates: dict[str, TraceTurnIdentity] = {}
        pending = (
            *self._interactive_trace_windows.values(),
            *self._background_trace_windows.values(),
        )
        for candidate in pending:
            if candidate.turn_id == window.turn_id:
                continue
            if _trace_intervals_overlap(
                window.started_at,
                completed_at,
                candidate.started_at,
                None,
            ):
                candidates[candidate.turn_id] = TraceTurnIdentity(
                    candidate.turn_id,
                    candidate.prompt,
                    candidate.session_id,
                    candidate.task_id,
                )
        for candidate in self._trace_turns:
            if candidate.turn_id == window.turn_id:
                continue
            if _trace_intervals_overlap(
                window.started_at,
                completed_at,
                candidate.started_at,
                candidate.completed_at,
            ):
                candidates[candidate.turn_id] = TraceTurnIdentity(
                    candidate.turn_id,
                    candidate.prompt,
                    candidate.session_id,
                    candidate.task_id,
                )
        return tuple(candidates.values())

    def _events_for_turn(self, turn_id: str) -> tuple[AgentEvent, ...]:
        with self._interactive_events_lock:
            return tuple(
                event
                for event in self._interactive_events
                if event.turn_id == turn_id
            )

    def _record_collector_failure(self, stage: str, error: BaseException) -> None:
        detail = f"{stage}: {type(error).__name__}: {error}"
        with self._trace_lock:
            self._collector_health_state = CollectorHealthState.UNHEALTHY
            self._collector_errors.append(detail)
            self._unscoped_collector_errors.append(detail)
        self.environment.ledger.record(
            "network_collector",
            "collector_failure",
            {"stage": stage, "error_type": type(error).__name__},
        )

    def _capture_trace_evidence(
        self,
        request: EvidenceRequest,
        *,
        tool_records: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        if self._collector_manager is None:
            return ()
        with self._trace_lock:
            all_turns = tuple(self._trace_turns)
            turns = tuple(
                turn
                for turn in all_turns
                if (
                    request.task_id is None or turn.task_id == request.task_id
                )
                and (
                    request.session_id is None
                    or turn.session_id == request.session_id
                )
            )
            selected_quality = self._combine_trace_quality(
                *(
                    self._trace_quality_by_turn.get(
                        turn.turn_id,
                        _TraceCollectorQuality(),
                    )
                    for turn in turns
                ),
                _TraceCollectorQuality(
                    health_state=(
                        CollectorHealthState.UNHEALTHY
                        if self._unscoped_collector_errors
                        else CollectorHealthState.HEALTHY
                    ),
                    errors=tuple(self._unscoped_collector_errors),
                    failed=bool(self._unscoped_collector_errors),
                ),
            )
            selected_turn_ids = {turn.turn_id for turn in turns}
            network_artifacts = tuple(
                dict(item)
                for item in self._network_artifacts
                if item.get("turn_id") in selected_turn_ids
            )
        trace = self._trace_adapter.build(
            run_id=self.environment.run_id,
            turns=turns,
            tool_records=tool_records,
            test_case_id=self._test_case_id,
            collector_health=selected_quality.health_state.value,
            lost_event_count=selected_quality.lost_records,
            limitations=selected_quality.limitations,
        )
        return self._trace_records(
            request,
            trace,
            turns=turns,
            collector_errors=selected_quality.errors,
            network_artifacts=network_artifacts,
        )

    def _trace_records(
        self,
        request: EvidenceRequest,
        trace: AgentTrace,
        *,
        turns: tuple[TraceTurnObservation, ...],
        collector_errors: tuple[str, ...],
        network_artifacts: tuple[dict[str, JsonValue], ...],
    ) -> tuple[EvidenceRecord, ...]:
        observed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        source = EvidenceSource(
            provider="agent_test_tool",
            channel="run_scoped_https_mitm",
            authority=EvidenceAuthority.EVALUATOR_OBSERVED,
            product="codebuddy",
            observed_at=observed_at,
        )
        trace_payload = trace.to_payload()
        self._archive_atif_trajectories(trace)
        correlations = self._trace_correlation(trace, turns)
        model_calls: list[tuple[str, str, dict[str, JsonValue]]] = []
        for session in trace_payload["sessions"]:
            session_id = str(session["session_id"])
            for turn in session["turns"]:
                turn_id = str(turn["turn_id"])
                for call in turn["model_calls"]:
                    model_calls.append((session_id, turn_id, call))
        exchanges = [
            self._network_exchange_metadata(exchange)
            for turn in turns
            for exchange in turn.exchanges
        ]
        network_failures = [
            exchange
            for turn in turns
            for exchange in turn.exchanges
            if exchange.get("error")
            or exchange.get("request_complete") is False
            or exchange.get("response_complete") is False
        ]
        network_truncations = [
            exchange
            for turn in turns
            for exchange in turn.exchanges
            if exchange.get("request_body_truncated") is True
            or exchange.get("response_body_truncated") is True
        ]
        trace_status = {
            TraceReadyState.READY: EvidenceStatus.AVAILABLE,
            TraceReadyState.PARTIAL: EvidenceStatus.UNVERIFIED,
            TraceReadyState.REPLAYED: EvidenceStatus.UNVERIFIED,
            TraceReadyState.UNAVAILABLE: EvidenceStatus.MISSING,
        }[trace.ready_state]
        network_status = (
            EvidenceStatus.ERROR
            if collector_errors or network_failures
            else EvidenceStatus.UNVERIFIED
            if network_truncations
            or trace.collector_health != CollectorHealthState.HEALTHY.value
            else EvidenceStatus.AVAILABLE
            if exchanges
            else EvidenceStatus.MISSING
        )
        common_limitations = (
            "该证据通过评测方运行级 HTTPS 代理采集，属于 Q04 网络抓包，不是 Agent 原生日志。",
            "只覆盖继承本次代理环境的 CodeBuddy 进程流量，不证明未观察通道没有副作用。",
            "回环代理不能从密码学上证明连接一定由目标 OS 进程发起。",
            "客户端网络请求不证明服务端数据最终持久化或安全审计记录已经产生。",
        )
        contexts = [
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "model_call_id": call["model_call_id"],
                "request_id": call["request_id"],
                "messages": [
                    item for item in call["messages"] if item["phase"] == "request"
                ],
            }
            for session_id, turn_id, call in model_calls
        ]
        outputs = [
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "model_call_id": call["model_call_id"],
                "request_id": call["request_id"],
                "messages": [
                    item for item in call["messages"] if item["phase"] == "response"
                ],
                "reasoning": call["reasoning"],
                "tool_calls": [
                    item
                    for item in call["tool_calls"]
                    if item["phase"] == "response"
                ],
            }
            for session_id, turn_id, call in model_calls
        ]
        tool_trace = [
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "model_call_id": call["model_call_id"],
                "tool_calls": call["tool_calls"],
                "tool_results": call["tool_results"],
            }
            for session_id, turn_id, call in model_calls
            if call["tool_calls"] or call["tool_results"]
        ]
        observed_tool_stages = tuple(
            dict.fromkeys(
                str(item["stage"])
                for entry in tool_trace
                for item in (*entry["tool_calls"], *entry["tool_results"])
            )
        )
        tool_proves = (
            (
                "本次 Trace 实际观察到的工具生命周期阶段："
                + "、".join(observed_tool_stages)
            ),
        ) if observed_tool_stages else ()
        records = (
            EvidenceRecord(
                "network_exchange_trace",
                "network_evidence",
                request.phase,
                {
                    "exchanges": exchanges,
                    "artifacts": [dict(item) for item in network_artifacts],
                },
                status=network_status,
                source=source,
                correlation=correlations,
                proves=("CodeBuddy 进程经显式代理实际发送和接收的 HTTP(S) 交换",),
                limitations=common_limitations,
            ),
            EvidenceRecord(
                "observed_model_context",
                "agent_trace_evidence",
                request.phase,
                {"model_calls": contexts},
                status=trace_status if contexts else EvidenceStatus.MISSING,
                source=source,
                correlation=correlations,
                proves=("模型请求中实际观察到的消息、角色、当前输入和历史上下文",),
                limitations=common_limitations,
            ),
            EvidenceRecord(
                "observed_model_output",
                "agent_trace_evidence",
                request.phase,
                {"model_calls": outputs},
                status=trace_status if outputs else EvidenceStatus.MISSING,
                source=source,
                correlation=correlations,
                proves=("模型网络响应中显式返回的文本、工具提议和推理摘要",),
                limitations=(
                    *common_limitations,
                    "不包含、恢复或推断模型未在响应中公开的隐藏思维链。",
                ),
            ),
            EvidenceRecord(
                "observed_tool_trace",
                "agent_trace_evidence",
                request.phase,
                {"model_calls": tool_trace},
                status=trace_status if tool_trace else EvidenceStatus.MISSING,
                source=source,
                correlation=correlations,
                proves=tool_proves,
                limitations=(
                    *common_limitations,
                    "模型响应中的工具调用只证明提议；实际执行需由运行时或 Mock MCP 证据确认。",
                ),
            ),
            EvidenceRecord(
                "reconstructed_agent_trace",
                "agent_trace_evidence",
                request.phase,
                trace_payload,
                status=trace_status,
                source=source,
                correlation=correlations,
                proves=("由网络、公开运行流及受控工具证据重建的 Agent 执行顺序",),
                limitations=common_limitations,
            ),
            EvidenceRecord(
                "collector_quality_report",
                "collection_diagnostic",
                request.phase,
                {
                    "health": trace.collector_health,
                    "ready_state": trace.ready_state.value,
                    "lost_event_count": trace.lost_event_count,
                    "turn_count": sum(len(session.turns) for session in trace.sessions),
                    "model_call_count": len(model_calls),
                    "network_failure_count": len(network_failures),
                    "network_truncation_count": len(network_truncations),
                    "errors": list(collector_errors),
                    "limitations": list(trace.limitations),
                },
                source=source,
                correlation=correlations,
                proves=("本次证据获取器的健康度、完整性和已知限制",),
                limitations=("健康报告不替代具体业务事实证据。",),
            ),
        )
        return records

    def _archive_atif_trajectories(self, trace: AgentTrace) -> None:
        """Export portable ATIF without changing the authoritative Trace result."""

        try:
            trajectories = self._atif_converter.convert(trace)
        except Exception as error:
            # ATIF is an auxiliary interoperability artifact during migration.
            self.environment.ledger.record(
                "atif_exporter",
                "export_failed",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            return
        try:
            multiple = len(trajectories) > 1
            references: list[dict[str, JsonValue]] = []
            for trajectory in trajectories:
                payload = trajectory.to_payload()
                name = self._atif_artifact_name(payload, multiple=multiple)
                path = self._save_or_reuse_trace_artifact(name, payload)
                references.append(self._artifact_reference(path, turn_id="", kind="atif"))
            self.environment.ledger.record(
                "atif_exporter",
                "export_completed",
                {"trajectory_count": len(trajectories), "artifacts": references},
            )
        except (TypeError, ValueError, KeyError) as error:
            self.environment.ledger.record(
                "atif_exporter",
                "export_failed",
                {"error_type": type(error).__name__, "message": str(error)},
            )

    def _atif_artifact_name(
        self,
        payload: dict[str, JsonValue],
        *,
        multiple: bool,
    ) -> str:
        if multiple:
            return self._trace_artifact_name("trajectory", payload)
        path = self.environment.evidence_directory / "trajectory.json"
        if not path.exists():
            return "trajectory"
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._trace_artifact_name("trajectory", payload)
        redacted = self.environment.ledger.redact(payload)
        return (
            "trajectory"
            if existing == redacted
            else self._trace_artifact_name("trajectory", payload)
        )

    @staticmethod
    def _network_evidence_exchange(
        exchange: Mapping[str, JsonValue] | object,
    ) -> dict[str, JsonValue]:
        if not isinstance(exchange, Mapping):
            return {}
        payload = dict(exchange)
        path = payload.get("path")
        if not isinstance(path, str) or path.split("?", 1)[0] != "/v2/chat/completions":
            payload["request_body"] = "<omitted-non-model-payload>"
            payload["response_body"] = "<omitted-non-model-payload>"
        return payload

    def _archive_network_turn(
        self,
        window: _TraceWindowStart,
        exchanges: tuple[Mapping[str, JsonValue], ...],
        *,
        references: list[dict[str, JsonValue]] | None = None,
    ) -> tuple[dict[str, JsonValue], ...]:
        """Archive bodies in bounded chunks and return verifiable references."""

        saved = references if references is not None else []
        archived: list[dict[str, JsonValue]] = []
        for exchange_index, exchange in enumerate(exchanges):
            payload = self._network_evidence_exchange(exchange)
            exchange_id = str(payload.get("exchange_id") or exchange_index)
            for field in ("request_body", "response_body"):
                body = payload.pop(field, None)
                if not isinstance(body, str):
                    continue
                if body == "<omitted-non-model-payload>":
                    payload[field] = body
                    continue
                body_references = self._save_text_artifact_chunks(
                    turn_id=window.turn_id,
                    exchange_id=exchange_id,
                    field=field,
                    value=body,
                    references=saved,
                )
                payload[f"{field}_artifacts"] = [
                    {
                        "filename": item["filename"],
                        "sha256": item["sha256"],
                        "bytes": item["bytes"],
                        "chunk_index": item["chunk_index"],
                    }
                    for item in body_references
                ]
            archived.append(payload)

        manifest_reference = next(
            (
                item
                for item in saved
                if item.get("turn_id") == window.turn_id
                and item.get("kind") == "turn_manifest"
            ),
            None,
        )
        if manifest_reference is None:
            manifest_payload = {
                "turn_id": window.turn_id,
                "session_id": window.session_id,
                "task_id": window.task_id,
                "exchanges": archived,
            }
            artifact_path = self._save_or_reuse_trace_artifact(
                self._trace_artifact_name("network_turn", manifest_payload),
                manifest_payload,
            )
            saved.append(
                self._artifact_reference(
                    artifact_path,
                    turn_id=window.turn_id,
                    kind="turn_manifest",
                )
            )
        return tuple(saved)

    def _save_text_artifact_chunks(
        self,
        *,
        turn_id: str,
        exchange_id: str,
        field: str,
        value: str,
        references: list[dict[str, JsonValue]] | None = None,
    ) -> tuple[dict[str, JsonValue], ...]:
        # 100k characters stay below the ledger's 1 MiB per-artifact bound even
        # for four-byte UTF-8 text plus JSON escaping and metadata.
        chunks = [
            value[index : index + 100_000]
            for index in range(0, len(value), 100_000)
        ] or [""]
        saved = references if references is not None else []
        body_references: list[dict[str, JsonValue]] = []
        for chunk_index, chunk in enumerate(chunks):
            existing = next(
                (
                    item
                    for item in saved
                    if item.get("turn_id") == turn_id
                    and item.get("kind") == field
                    and item.get("exchange_id") == exchange_id
                    and item.get("chunk_index") == chunk_index
                ),
                None,
            )
            if existing is not None:
                body_references.append(existing)
                continue
            chunk_payload = {
                "turn_id": turn_id,
                "exchange_id": exchange_id,
                "field": field,
                "chunk_index": chunk_index,
                "chunk_count": len(chunks),
                "content": chunk,
            }
            artifact_path = self._save_or_reuse_trace_artifact(
                self._trace_artifact_name("network_body", chunk_payload),
                chunk_payload,
            )
            reference = self._artifact_reference(
                artifact_path,
                turn_id=turn_id,
                kind=field,
                extra={
                    "exchange_id": exchange_id,
                    "chunk_index": chunk_index,
                },
            )
            saved.append(reference)
            body_references.append(reference)
        return tuple(body_references)

    def _trace_artifact_name(self, prefix: str, payload: JsonValue) -> str:
        encoded = json.dumps(
            self.environment.ledger.redact(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:32]}"

    def _save_or_reuse_trace_artifact(
        self,
        name: str,
        payload: JsonValue,
    ) -> Path:
        ledger = self.environment.ledger
        filename = f"{name}.json"
        path = ledger.directory / filename
        if path.exists():
            registered = getattr(ledger, "_artifacts", {}).get(filename)
            if registered is None:
                path.unlink()
            else:
                content = path.read_bytes()
                if (
                    len(content) != registered.get("bytes")
                    or hashlib.sha256(content).hexdigest()
                    != registered.get("sha256")
                ):
                    raise RuntimeError(
                        "Trace artifact exists but does not match its ledger anchor"
                    )
                anchored = any(
                    event.get("source") == "ledger"
                    and event.get("kind") == "artifact_saved"
                    and event.get("data", {}).get("filename") == filename
                    for event in ledger.events
                )
                if not anchored:
                    ledger.record("ledger", "artifact_saved", registered)
                return path
        return ledger.save_artifact(name, payload)

    @staticmethod
    def _artifact_reference(
        artifact_path: Path,
        *,
        turn_id: str,
        kind: str,
        extra: Mapping[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        content = artifact_path.read_bytes()
        reference: dict[str, JsonValue] = {
            "turn_id": turn_id,
            "kind": kind,
            "filename": artifact_path.name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
        if extra:
            reference.update(extra)
        return reference

    @staticmethod
    def _network_exchange_metadata(
        exchange: Mapping[str, JsonValue] | object,
    ) -> dict[str, JsonValue]:
        if not isinstance(exchange, Mapping):
            return {}
        payload = dict(exchange)
        for field in ("request_body", "response_body"):
            value = payload.pop(field, "")
            if isinstance(value, str):
                payload[f"{field}_sha256"] = hashlib.sha256(
                    value.encode("utf-8")
                ).hexdigest()
        return payload

    def _trace_correlation(
        self,
        trace: AgentTrace,
        turns: tuple[TraceTurnObservation, ...],
    ) -> EvidenceCorrelation:
        session_ids = tuple(session.session_id for session in trace.sessions)
        turn_ids = tuple(
            turn.turn_id for session in trace.sessions for turn in session.turns
        )
        request_ids = tuple(
            dict.fromkeys(
                call.request_id
                for session in trace.sessions
                for turn in session.turns
                for call in turn.model_calls
                if call.request_id
            )
        )
        tool_ids = tuple(
            dict.fromkeys(
                item.tool_call_id
                for session in trace.sessions
                for turn in session.turns
                for call in turn.model_calls
                for item in (*call.tool_calls, *call.tool_results)
            )
        )
        return EvidenceCorrelation(
            run_id=self.environment.run_id,
            session_ids=session_ids,
            request_ids=request_ids,
            turn_ids=turn_ids,
            task_ids=tuple(
                dict.fromkeys(turn.task_id for turn in turns if turn.task_id)
            ),
            tool_use_ids=tool_ids,
        )

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
        if self._has_attempted_session:
            raise RuntimeError("必须在 Agent 会话开始前准备本地状态")
        return self.local_state.execute(LocalStateAction.PREPARE, request)

    def restore_local_state(self, request: LocalStateRequest) -> tuple[EvidenceRecord, ...]:
        return self.local_state.execute(LocalStateAction.RESTORE, request)

    def prepare_memory_state(
        self,
        request: MemoryStateRequest,
    ) -> tuple[EvidenceRecord, ...]:
        if self._has_attempted_session:
            raise RuntimeError("必须在 Agent 会话开始前保存记忆状态基线")
        if self.memory_state is None:
            raise RuntimeError("CodeBuddy 记忆状态控制器未配置")
        return self._record_memory_evidence(self.memory_state.prepare(request))

    def capture_memory_state(
        self,
        request: MemoryStateRequest,
    ) -> tuple[EvidenceRecord, ...]:
        if self.memory_state is None:
            raise RuntimeError("CodeBuddy 记忆状态控制器未配置")
        return self._record_memory_evidence(self.memory_state.capture(request))

    def restore_memory_state(
        self,
        request: MemoryStateRequest,
    ) -> tuple[EvidenceRecord, ...]:
        if self.memory_state is None:
            raise RuntimeError("CodeBuddy 记忆状态控制器未配置")
        return self._record_memory_evidence(self.memory_state.restore(request))

    def _record_memory_evidence(
        self,
        records: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        self._memory_records.extend(records)
        for record in records:
            self.environment.ledger.record(
                "codebuddy_memory",
                record.evidence_id,
                asdict(record),
                record.correlation.run_id,
            )
        return records

    def close(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        if self._environment is not None:
            try:
                self._environment.begin_shutdown(allow_active=True)
            except BaseException as error:
                errors.append(error)
        try:
            self.driver.close(session_id=self._session_id)
        except BaseException as error:
            errors.append(error)
        with self._trace_lock:
            pending = (
                *(
                    ("interactive", turn_id, window)
                    for turn_id, window in self._interactive_trace_windows.items()
                ),
                *(
                    ("background", task_id, window)
                    for task_id, window in self._background_trace_windows.items()
                ),
            )
        window_errors: list[BaseException] = []
        for kind, key, window in pending:
            try:
                self._finish_trace_window(
                    window,
                    stream_events=self._events_for_turn(window.turn_id),
                )
            except BaseException as error:
                window_errors.append(error)
            finally:
                with self._trace_lock:
                    windows = (
                        self._interactive_trace_windows
                        if kind == "interactive"
                        else self._background_trace_windows
                    )
                    if (
                        window.turn_id in self._finalized_trace_window_ids
                        and windows.get(key) is window
                    ):
                        windows.pop(key)
        if window_errors:
            raise BaseExceptionGroup(
                "Agent Model cleanup failed",
                [*errors, *window_errors],
            )
        if self._collector_manager is not None:
            try:
                self._collector_manager.close()
            except BaseException as error:
                raise BaseExceptionGroup(
                    "Agent Model cleanup failed",
                    [*errors, error],
                ) from None
        for cleanup in (
            self.mock_tool.close,
            self.memory_state.close if self.memory_state is not None else lambda: None,
        ):
            try:
                cleanup()
            except BaseException as error:
                errors.append(error)
        if self._environment is not None:
            try:
                self._environment.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Agent Model cleanup failed", errors)
        self._closed = True
