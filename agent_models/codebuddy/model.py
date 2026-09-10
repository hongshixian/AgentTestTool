"""CodeBuddy implementation of the public Agent Model facade."""

from __future__ import annotations

import subprocess
import threading
import uuid
from dataclasses import asdict
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
                raise
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
            handle = self.driver.start_background_task(
                prompt,
                name=name,
                timeout=timeout,
                allow_tools=allow_tools,
                permission_policy=permission_policy,
                extra_args=self.mock_tool.extra_args if allow_tools else (),
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
            records = (
                external_records
                + stream_records
                + background_records
                + self.mock_tool.capture(request)
                + self.environment.capture(request)
                + tuple(self._memory_records)
            )
            self.environment.ledger.save_artifact(f"capture_{uuid.uuid4().hex}",
                                                  [asdict(record) for record in records])
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
        for cleanup in (
            self.mock_tool.close,
            self.memory_state.close if self.memory_state is not None else lambda: None,
            self._environment.close if self._environment is not None else lambda: None,
        ):
            try:
                cleanup()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Agent Model cleanup failed", errors)
        self._closed = True
