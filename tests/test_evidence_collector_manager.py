"""Verify evidence collector lifecycle orchestration and failure handling."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from evidence_collectors.base import (
    CollectionContext,
    CollectorHealth,
    CollectorHealthState,
    CollectorLaunchConfig,
    CollectorResult,
    CollectorStatus,
    EvidenceCollector,
    EvidenceCursor,
    ObservationWindow,
)
from evidence_collectors.manager import (
    EvidenceCollectionError,
    EvidenceCollectorManager,
    ManagerState,
)


class RecordingCollector(EvidenceCollector):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        environment: Mapping[str, str] | None = None,
        fail_at: str | None = None,
    ) -> None:
        self._name = name
        self.events = events
        self.environment = {} if environment is None else dict(environment)
        self.fail_at = fail_at
        self.cursor = 0
        self.close_attempts = 0

    @property
    def name(self) -> str:
        return self._name

    def _record(self, stage: str) -> None:
        self.events.append(f"{self.name}:{stage}")
        if self.fail_at == stage:
            raise RuntimeError(f"{self.name} failed at {stage}")

    def prepare(self, context: CollectionContext) -> CollectorLaunchConfig:
        self._record("prepare")
        assert context.run_id == "run-001"
        return CollectorLaunchConfig(self.environment)

    def start(self) -> None:
        self._record("start")

    def checkpoint(self, label: str) -> EvidenceCursor:
        self._record(f"checkpoint-{label}")
        self.cursor += 1
        return EvidenceCursor(self.name, str(self.cursor))

    def collect(self, window: ObservationWindow) -> CollectorResult:
        self._record("collect")
        start, end = window.cursors_for(self.name)
        return CollectorResult(
            self.name,
            CollectorStatus.AVAILABLE,
            CollectorHealth(),
            ({"start": start.value, "end": end.value},),
        )

    def drain(self, timeout_seconds: float) -> CollectorResult:
        self._record("drain")
        return CollectorResult(
            self.name,
            CollectorStatus.AVAILABLE,
            CollectorHealth(),
            ({"timeout_seconds": timeout_seconds},),
        )

    def close(self) -> None:
        self.close_attempts += 1
        self._record("close")


@pytest.fixture
def context(tmp_path: Path) -> CollectionContext:
    return CollectionContext(
        run_id="run-001",
        test_case_id="ATS-TEST-01",
        product="codebuddy",
        workspace=tmp_path / "workspace",
        evidence_dir=tmp_path / "evidence",
        secrets=("test-secret",),
    )


def test_manager_runs_collectors_and_merges_process_environment(
    context: CollectionContext,
) -> None:
    events: list[str] = []
    manager = EvidenceCollectorManager(
        (
            RecordingCollector("network", events, environment={"HTTPS_PROXY": "proxy"}),
            RecordingCollector(
                "stream", events, environment={"RUN_SCOPE": "run-001"}
            ),
        )
    )

    launch = manager.prepare(context)
    manager.start()
    before = manager.checkpoint("before")
    after = manager.checkpoint("after")
    batch = manager.collect(ObservationWindow(before, after, "agent-turn"))
    drained = manager.drain(2)
    manager.close()

    assert launch.environment_overrides == {
        "HTTPS_PROXY": "proxy",
        "RUN_SCOPE": "run-001",
    }
    assert manager.environment_overrides == launch.environment_overrides
    assert batch.results["network"].observations == ({"start": "1", "end": "2"},)
    assert drained.results["stream"].observations == ({"timeout_seconds": 2.0},)
    assert events[-2:] == ["stream:close", "network:close"]
    assert manager.state is ManagerState.CLOSED


def test_same_environment_override_is_allowed_but_conflict_fails_closed(
    context: CollectionContext,
) -> None:
    same_events: list[str] = []
    same = EvidenceCollectorManager(
        (
            RecordingCollector("one", same_events, environment={"TRACE_ID": "1"}),
            RecordingCollector("two", same_events, environment={"TRACE_ID": "1"}),
        )
    )
    assert same.prepare(context).environment_overrides == {"TRACE_ID": "1"}
    same.close()

    events: list[str] = []
    conflicting = EvidenceCollectorManager(
        (
            RecordingCollector("one", events, environment={"TRACE_ID": "1"}),
            RecordingCollector("two", events, environment={"TRACE_ID": "2"}),
        )
    )

    with pytest.raises(EvidenceCollectionError, match="environment override") as exc:
        conflicting.prepare(context)

    assert exc.value.failures[0].collector_name == "two"
    assert events[-2:] == ["two:close", "one:close"]
    assert conflicting.state is ManagerState.CLOSED


def test_start_failure_is_reported_and_all_prepared_collectors_close_in_reverse(
    context: CollectionContext,
) -> None:
    events: list[str] = []
    manager = EvidenceCollectorManager(
        (
            RecordingCollector("one", events),
            RecordingCollector("two", events, fail_at="start"),
            RecordingCollector("three", events),
        )
    )
    manager.prepare(context)

    with pytest.raises(EvidenceCollectionError, match="two failed at start") as exc:
        manager.start()

    assert exc.value.failures[0].stage == "start"
    assert events[-3:] == ["three:close", "two:close", "one:close"]
    assert manager.state is ManagerState.CLOSED


def test_checkpoint_and_collection_failures_are_not_silenced(
    context: CollectionContext,
) -> None:
    checkpoint_events: list[str] = []
    checkpoint_manager = EvidenceCollectorManager(
        (
            RecordingCollector("one", checkpoint_events, fail_at="checkpoint-before"),
            RecordingCollector("two", checkpoint_events),
        )
    )
    checkpoint_manager.prepare(context)
    checkpoint_manager.start()

    with pytest.raises(EvidenceCollectionError) as checkpoint_error:
        checkpoint_manager.checkpoint("before")

    assert checkpoint_error.value.failures[0].collector_name == "one"
    assert "two:checkpoint-before" in checkpoint_events
    checkpoint_manager.close()

    collection_events: list[str] = []
    collection_manager = EvidenceCollectorManager(
        (
            RecordingCollector("one", collection_events, fail_at="collect"),
            RecordingCollector("two", collection_events),
        )
    )
    collection_manager.prepare(context)
    collection_manager.start()
    before = collection_manager.checkpoint("before")
    after = collection_manager.checkpoint("after")

    with pytest.raises(EvidenceCollectionError) as collection_error:
        collection_manager.collect(ObservationWindow(before, after, "turn"))

    assert collection_error.value.failures[0].collector_name == "one"
    assert "two:collect" in collection_events
    collection_manager.close()


def test_running_context_manager_always_closes_and_preserves_body_failure(
    context: CollectionContext,
) -> None:
    events: list[str] = []
    manager = EvidenceCollectorManager(
        (RecordingCollector("one", events), RecordingCollector("two", events))
    )

    with pytest.raises(LookupError, match="body failed"):
        with manager.running(context) as active:
            assert active.state is ManagerState.STARTED
            raise LookupError("body failed")

    assert events[-2:] == ["two:close", "one:close"]
    assert manager.state is ManagerState.CLOSED


def test_running_context_manager_closes_on_base_exception(
    context: CollectionContext,
) -> None:
    events: list[str] = []
    manager = EvidenceCollectorManager((RecordingCollector("one", events),))

    with pytest.raises(KeyboardInterrupt):
        with manager.running(context):
            raise KeyboardInterrupt

    assert events[-1] == "one:close"
    assert manager.state is ManagerState.CLOSED


def test_lifecycle_order_and_duplicate_names_are_rejected(
    context: CollectionContext,
) -> None:
    events: list[str] = []
    manager = EvidenceCollectorManager((RecordingCollector("one", events),))

    with pytest.raises(RuntimeError, match="expected prepared"):
        manager.start()
    with pytest.raises(ValueError, match="unique"):
        EvidenceCollectorManager(
            (RecordingCollector("same", events), RecordingCollector("same", events))
        )

    manager.prepare(context)
    with pytest.raises(RuntimeError, match="expected new"):
        manager.prepare(context)
    manager.close()


def test_close_failure_keeps_manager_retryable(context: CollectionContext) -> None:
    events: list[str] = []
    collector = RecordingCollector("one", events, fail_at="close")
    manager = EvidenceCollectorManager((collector,))
    manager.prepare(context)
    manager.start()

    with pytest.raises(EvidenceCollectionError, match="failed at close"):
        manager.close()

    assert manager.state is ManagerState.STARTED
    collector.fail_at = None
    manager.close()
    assert collector.close_attempts == 2
    assert manager.state is ManagerState.CLOSED


def test_available_result_requires_healthy_collector() -> None:
    with pytest.raises(ValueError, match="requires a healthy collector"):
        CollectorResult(
            "network",
            CollectorStatus.AVAILABLE,
            CollectorHealth(state=CollectorHealthState.DEGRADED),
        )


def test_collection_result_exposes_immutable_diagnostics() -> None:
    resource_limits = ["connections"]
    nested = {"counts": [1]}
    error_types = {"timeout"}
    result = CollectorResult(
        "fixture",
        CollectorStatus.UNVERIFIED,
        CollectorHealth(CollectorHealthState.DEGRADED, "bounded"),
        diagnostics={
            "resource_limits": resource_limits,
            "nested": nested,
            "error_types": error_types,
        },
    )

    resource_limits.append("bytes")
    nested["counts"].append(2)
    error_types.add("connection")

    assert result.diagnostics["resource_limits"] == ("connections",)
    assert result.diagnostics["nested"] == {"counts": (1,)}
    assert result.diagnostics["error_types"] == frozenset({"timeout"})
    with pytest.raises(TypeError):
        result.diagnostics["other"] = True
    with pytest.raises(TypeError):
        result.diagnostics["nested"]["other"] = True
    with pytest.raises(AttributeError):
        result.diagnostics["resource_limits"].append("bytes")
