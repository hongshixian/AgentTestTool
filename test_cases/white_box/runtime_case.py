"""Shared four-state execution for implemented source-runtime white-box cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from agent_models import (
    AgentModel,
    EvidenceAuthority,
    EvidencePhase,
    EvidenceRequirement,
    EvidenceStatus,
    WhiteBoxCaseRequest,
    WhiteBoxCaseResult,
)
from test_cases.pipeline import PipelinePhase, pipeline_phase


_REQUIRED_EVIDENCE = {
    "white_box_code",
    "white_box_spy",
    "white_box_state",
    "white_box_control",
}
_EVIDENCE_AUTHORITIES = {
    "white_box_code": (EvidenceAuthority.PRODUCT_RUNTIME,),
    "white_box_spy": (EvidenceAuthority.PRODUCT_RUNTIME,),
    "white_box_state": (EvidenceAuthority.EVALUATOR_OBSERVED,),
    "white_box_control": (EvidenceAuthority.EVALUATOR_CONTROLLED,),
}
_REQUIREMENTS = tuple(
    EvidenceRequirement(
        evidence_id=evidence_id,
        phases=(EvidencePhase.AFTER,),
        authorities=_EVIDENCE_AUTHORITIES[evidence_id],
        require_source=True,
        require_run_correlation=True,
        require_observed_at=True,
    )
    for evidence_id in sorted(_REQUIRED_EVIDENCE)
)
_REQUIRED_FIELDS = {
    "white_box_code": {
        "Case_ID", "Repeat_Index", "Commit_ID", "Build_Config", "Entry_Point",
        "Source_Location", "Source_Hashes", "Dependency_Command",
        "Dependency_Exit_Code", "Test_Command", "Test_Exit_Code", "Branch_Tag",
        "Expected_Branch_Tags", "Visited_Branch_Tags",
    },
    "white_box_spy": {
        "Case_ID", "Phase_ID", "Events", "Uncalled_Functions",
    },
    "white_box_state": {
        "Case_ID", "Phase_ID", "State", "User_ID", "Instance_ID", "Task_ID",
        "Object_ID", "Bytes_After_Cleanup", "Resource_Limits",
        "Cleanup_Completed",
    },
    "white_box_control": {
        "Run_ID", "Case_ID", "Repeat_Index", "Phase_ID", "Collector_Ready",
        "Positive_Control_OK", "Collection_Complete", "Coverage_Manifest",
        "User_Action", "Action_Ack_At", "Observation_End_At", "Clock_Source",
        "Dropped_Event_Count",
    },
}


@dataclass(frozen=True, slots=True)
class WhiteBoxRuntimeCaseSpec:
    """Workbook-derived execution contract for one implemented white-box case."""

    case_id: str
    variants: tuple[str, ...]
    expected_metrics: tuple[tuple[str, int], ...]
    pass_reason: str
    timeout_seconds: float = 120

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.variants or not self.expected_metrics:
            raise ValueError("white-box runtime case spec must be complete")
        if any(type(value) is not int for _, value in self.expected_metrics):
            raise ValueError("white-box expected metrics must be integer counts")
        if len({name for name, _ in self.expected_metrics}) != len(self.expected_metrics):
            raise ValueError("white-box expected metric names must be unique")


def _evidence_shape_failures(result: WhiteBoxCaseResult) -> tuple[str, ...]:
    failures: list[str] = []
    for evidence_id, fields in _REQUIRED_FIELDS.items():
        records = tuple(
            record for record in result.evidence.records
            if record.evidence_id == evidence_id and record.available
        )
        if len(records) != 1 or not isinstance(records[0].data, dict):
            failures.append(f"{evidence_id}（必须恰有一条 available 对象证据）")
            continue
        missing = sorted(fields - set(records[0].data))
        if missing:
            failures.append(f"{evidence_id}（缺少字段：{', '.join(missing)}）")
    return tuple(failures)


def execute_runtime_white_box_case(
    case: Any,
    agent_model: AgentModel,
    request: pytest.FixtureRequest,
    spec: WhiteBoxRuntimeCaseSpec,
    *,
    repeat_index: int = 1,
) -> None:
    """Execute one source-runtime case and explicitly produce a four-state result."""
    with pipeline_phase(request, agent_model, PipelinePhase.CAPABILITY_CHECK, repeat_index=repeat_index):
        if spec.case_id not in agent_model.capabilities.white_box_case_ids:
            case.conclude_not_applicable(
                request,
                agent_model,
                reason=f"当前被测产品未声明 {spec.case_id} 白盒 Harness 能力",
            )

    with pipeline_phase(request, agent_model, PipelinePhase.ENVIRONMENT_SETUP, repeat_index=repeat_index):
        try:
            white_box_request = WhiteBoxCaseRequest(
                case_id=spec.case_id,
                repeat_index=repeat_index,
                timeout_seconds=spec.timeout_seconds,
                variants=spec.variants,
            )
        except Exception as error:
            case.conclude_failed(
                request, agent_model,
                reason=f"{spec.case_id} Harness 请求构造失败：{error}",
            )

    with pipeline_phase(request, agent_model, PipelinePhase.EXERCISE, repeat_index=repeat_index):
        try:
            result = agent_model.execute_white_box_case(white_box_request)
        except Exception as error:
            case.conclude_failed(
                request, agent_model,
                reason=f"{spec.case_id} 真实生产 Harness 执行失败：{error}",
            )

    with pipeline_phase(
        request,
        agent_model,
        PipelinePhase.EVIDENCE_PROJECTION,
        repeat_index=repeat_index,
        evidence_ids=tuple(sorted(_REQUIRED_EVIDENCE)),
        artifact_refs=result.artifact_refs,
    ):
        assert isinstance(result, WhiteBoxCaseResult)
        metrics = {metric.name: metric for metric in result.metrics}
        for name, expected in spec.expected_metrics:
            metric = metrics.get(name)
            if metric is None or metric.status is not EvidenceStatus.AVAILABLE:
                continue
            if type(metric.value) is not int or metric.value != expected:
                case.conclude_failed(
                    request,
                    agent_model,
                    reason=(
                        f"{spec.case_id} 已取得有效不符合证据："
                        f"{name}={metric.value!r}，预期 {expected}"
                    ),
                )

        missing = set(result.evidence.missing_evidence(_REQUIRED_EVIDENCE))
        missing.update(result.missing_evidence)
        missing.update(result.evidence.unmet_requirements(_REQUIREMENTS))
        missing.update(_evidence_shape_failures(result))
        if not result.execution_completed:
            case.conclude_failed(
                request, agent_model,
                reason=f"{spec.case_id} Harness 未完成真实生产路径",
            )
        if not result.cleanup_completed:
            case.conclude_failed(
                request, agent_model,
                reason=f"{spec.case_id} Harness 清理/复位未完成",
            )
        for name, _ in spec.expected_metrics:
            metric = metrics.get(name)
            if metric is None:
                missing.add(name)
            elif metric.status is not EvidenceStatus.AVAILABLE:
                missing.add(f"{name}（状态不是 available）")
        if missing:
            case.conclude_inconclusive(
                request,
                agent_model,
                reason=f"{spec.case_id} 功能路径已执行，但必需白盒证据不完整",
                missing_evidence=tuple(sorted(missing)),
                execution_completed=True,
            )

    with pipeline_phase(request, agent_model, PipelinePhase.ASSERTION, repeat_index=repeat_index):
        case.conclude_passed(request, agent_model, reason=spec.pass_reason)


__all__ = ["WhiteBoxRuntimeCaseSpec", "execute_runtime_white_box_case"]
