"""Compose evaluator-owned resources without replacing product security controls."""

from __future__ import annotations

import tempfile
import threading
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_models.environment.ledger import EvidenceLedger
from agent_models.environment.orchestration import ScenarioRunner
from agent_models.environment.receiver import HttpToolReceiver
from agent_models.environment.tool_runtime import ToolRuntime, ToolRuntimeSnapshot
from agent_models.environment.workspace import WorkspaceManager, WorkspaceSnapshot
from agent_models.evidence import (
    EvidenceAuthority,
    EvidenceBundle,
    EvidenceCorrelation,
    EvidenceRecord,
    EvidenceRequest,
    EvidenceSource,
    JsonValue,
)
from agent_models.result import TurnResult
from agent_models.tools import ToolSuite


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """An in-memory checkpoint; restoring it never rewinds collected evidence."""

    run_id: str
    workspace: WorkspaceSnapshot
    tools: ToolRuntimeSnapshot | None


class ManagedActivity:
    """Keep the controlled environment leased while an external process is live."""

    def __init__(
        self,
        environment: ControlledEnvironment,
        name: str,
        correlation_id: str,
    ) -> None:
        self.environment = environment
        self.name = name
        self.correlation_id = correlation_id
        self._closed = False

    def close(self, error: BaseException | None = None) -> None:
        if self._closed:
            return
        self._closed = True
        self.environment._finish_activity(
            self.name,
            self.correlation_id,
            error=error,
        )


class ControlledEnvironment:
    """A local test environment, not an OS sandbox or a product identity observer.

    Callers must stop independent writers before snapshot/restore. The activity
    guard covers model turns; the receiver pause covers this environment's HTTP
    requests. Processes outside those channels remain the caller's responsibility.
    """

    def __init__(self, workspace: Path, *, evidence_directory: Path | None = None,
                 assets_root: Path | None = None, run_id: str | None = None,
                 secrets: Sequence[str] = (), request_timeout: float = 30) -> None:
        self.workspace = WorkspaceManager(
            workspace, assets_root=assets_root or Path(__file__).resolve().parents[2] / "assets"
        )
        directory = (Path(evidence_directory) if evidence_directory is not None else
                     Path(tempfile.mkdtemp(prefix="agent-test-evidence-")))
        self.ledger = EvidenceLedger(directory, run_id=run_id, secrets=secrets,
                                     workspace=self.workspace.root)
        self.run_id = self.ledger.run_id
        self.runner = ScenarioRunner(event_sink=self.ledger.record)
        self.runtime: ToolRuntime | None = None
        self.receiver: HttpToolReceiver | None = None
        self.request_timeout = request_timeout
        self._lock = threading.RLock()
        self._active = 0
        self._session_attempted = False
        self._closed = False
        self._closing = False
        self._errors: list[str] = []
        self.ledger.record("environment", "created", {"run_id": self.run_id})

    @property
    def evidence_directory(self) -> Path:
        return self.ledger.directory

    def _ensure_open(self) -> None:
        if self._closed or self._closing or self._errors:
            raise RuntimeError("controlled environment closed or unhealthy")
        if not self.ledger.health()["healthy"]:
            raise RuntimeError("evidence collector is unhealthy")

    @contextmanager
    def activity(self, name: str) -> Iterator[str]:
        """Prevent state restoration while a synchronous Agent operation is active."""
        lease = self.open_managed_activity(name)
        correlation = lease.correlation_id
        try:
            yield correlation
        except BaseException as error:
            try:
                lease.close(error)
            except BaseException as collector_error:
                raise BaseExceptionGroup("Agent operation and evidence recording failed",
                                         [error, collector_error]) from None
            raise
        else:
            lease.close()

    def open_managed_activity(self, name: str) -> ManagedActivity:
        """Lease the environment until a long-lived product operation is closed."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("activity name must be nonempty")
        correlation = uuid.uuid4().hex
        with self._lock:
            self._ensure_open()
            if self._active:
                raise RuntimeError("one Agent session cannot execute simultaneous operations")
            self.ledger.record("agent_model", "operation_started", {"name": name}, correlation)
            self._active += 1
            if name == "send_prompt":
                self._session_attempted = True
            if name == "interactive_session":
                self._session_attempted = True
        return ManagedActivity(self, name, correlation)

    def _finish_activity(
        self,
        name: str,
        correlation_id: str,
        *,
        error: BaseException | None,
    ) -> None:
        try:
            if error is None:
                self.ledger.record(
                    "agent_model",
                    "operation_completed",
                    {"name": name},
                    correlation_id,
                )
            else:
                self.ledger.record(
                    "agent_model",
                    "operation_failed",
                    {"name": name, "error_type": type(error).__name__},
                    correlation_id,
                )
        finally:
            with self._lock:
                if self._active <= 0:
                    raise RuntimeError("managed activity accounting underflow")
                self._active -= 1

    def configure_tools(self, suite: ToolSuite, *,
                        initial_state: dict[str, JsonValue] | None = None) -> None:
        with self._lock:
            self._ensure_open()
            if self.runtime is not None or self._active or self._session_attempted:
                raise RuntimeError("configure tools once, before starting Agent operations")
            runtime = ToolRuntime(suite, initial_state=initial_state,
                                  event_sink=self.ledger.record,
                                  default_timeout=self.request_timeout)
            try:
                receiver = HttpToolReceiver(runtime, event_sink=self.ledger.record,
                                            request_timeout=self.request_timeout)
                self.ledger.record("environment", "tools_configured",
                                   {"suite": asdict(suite), "initial_state": runtime.state})
            except BaseException:
                runtime.close()
                if "receiver" in locals():
                    receiver.close()
                raise
            self.runtime, self.receiver = runtime, receiver

    def record_turn(self, prompt: str, result: TurnResult, *, correlation_id: str) -> None:
        """Archive the full normalized turn, including untruncated raw output."""
        self.ledger.record("agent_model", "turn", {"prompt": prompt, "result": asdict(result)},
                           correlation_id)

    def health(self) -> dict[str, Any]:
        with self._lock:
            ledger = self.ledger.health()
            runner = self.runner.health()
            receiver = self.receiver.health() if self.receiver is not None else None
            runtime = self.runtime.healthy if self.runtime is not None else True
            return {"healthy": not self._closed and not self._closing and not self._errors
                    and ledger["healthy"] and runner["healthy"] and runtime
                    and (receiver is None or receiver["healthy"]),
                    "run_id": self.run_id, "closed": self._closed,
                    "active_operations": self._active, "errors": list(self._errors),
                    "ledger": ledger, "runner": runner, "receiver": receiver,
                    "runtime_healthy": runtime}

    def capture(self, request: EvidenceRequest) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            self._ensure_open()
            state = self.runtime.state if self.runtime is not None else {}
            data = self.ledger.redact({"run_id": self.run_id,
                                       "request": request.provider_payload(),
                                       "health": self.health(), "events": self.ledger.events,
                                       "simulated_state": state})
            return (
                EvidenceRecord(
                    "controlled_environment",
                    "runtime_evidence",
                    request.phase,
                    data,
                    source=EvidenceSource(
                        provider="controlled_environment",
                        channel="workspace_and_mock_runtime",
                        authority=EvidenceAuthority.EVALUATOR_CONTROLLED,
                    ),
                    correlation=EvidenceCorrelation(run_id=self.run_id),
                    proves=("评测方受控工作区和模拟工具在观察窗口内的状态",),
                    limitations=(
                        "不代表被测产品服务端身份、授权状态或内部安全日志。",
                    ),
                ),
            )

    def archive_bundle(self, bundle: EvidenceBundle, *, name: str = "evidence_bundle") -> Path:
        with self._lock:
            self._ensure_open()
            return self.ledger.archive_bundle(bundle, name=name)

    @contextmanager
    def _quiescent(self) -> Iterator[None]:
        with self._lock:
            self._ensure_open()
            if self._active or self.runner.health()["active_workers"]:
                raise RuntimeError("stop Agent operations and scenario workers before restoring state")
            with self.receiver.paused() if self.receiver is not None else nullcontext():
                yield

    def snapshot(self) -> EnvironmentSnapshot:
        with self._quiescent():
            tools = self.runtime.snapshot() if self.runtime is not None else None
            result = EnvironmentSnapshot(self.run_id, self.workspace.snapshot(), tools)
            self.ledger.record("environment", "snapshot", {"has_tools": tools is not None})
            return result

    def restore(self, snapshot: EnvironmentSnapshot) -> None:
        with self._quiescent():
            if snapshot.run_id != self.run_id:
                raise ValueError("checkpoint belongs to a different environment")
            if (snapshot.tools is None) != (self.runtime is None):
                raise ValueError("tool configuration changed since checkpoint")
            try:
                self.workspace.restore(snapshot.workspace)
                if self.runtime is not None:
                    self.runtime.restore(snapshot.tools)
                self.ledger.record("environment", "restored", {"run_id": self.run_id})
            except BaseException:
                self._errors.append("state restoration failed; state may be partially restored")
                raise

    def begin_shutdown(self, *, allow_active: bool = False) -> None:
        """Atomically reject new operations before product cleanup begins.

        A model may first close a long-lived product session while that session
        still owns the environment lease.  Other callers retain the stricter
        default and cannot begin shutdown while synchronous work is active.
        """
        with self._lock:
            if self._active and not allow_active:
                raise RuntimeError("cannot close during an Agent operation")
            self._closing = True

    def close(self) -> None:
        """Stop controlled work, retain evidence, and propagate every cleanup failure."""
        if self._closed:
            return
        self.begin_shutdown()
        errors: list[BaseException] = []
        for close in (self.runner.close,
                      self.receiver.close if self.receiver is not None else
                      self.runtime.close if self.runtime is not None else lambda: None):
            try:
                close()
            except BaseException as error:
                errors.append(error)
        if errors:
            self._errors.append("controlled activities were not confirmed stopped")
            # Keep the ledger open while surviving workers may still write evidence.
            raise BaseExceptionGroup("controlled environment cleanup failed", errors)
        try:
            self.ledger.record("environment", "closed", {"errors": list(self._errors)})
        except BaseException as error:
            errors.append(error)
        try:
            health = self.ledger.close()
            self._closed = True
            if not health["healthy"]:
                errors.append(RuntimeError("evidence archive integrity check failed"))
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("evidence finalization failed", errors)

    def __enter__(self) -> ControlledEnvironment:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
