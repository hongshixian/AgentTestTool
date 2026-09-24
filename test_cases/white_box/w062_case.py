"""Shared execution and assertion logic for the implemented W062 case."""

from __future__ import annotations

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


W062_VARIANTS = ("allow", "deny", "not_listed", "error")
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
        "Allowed_Executor_Calls", "Unauthorized_Executor_Calls",
    },
    "white_box_state": {
        "Case_ID", "Phase_ID", "State", "User_ID", "Instance_ID", "Task_ID",
        "Object_ID", "Bytes_After_Cleanup", "Resource_Limits",
        "Pending_Permissions_After", "Cleanup_Completed",
    },
    "white_box_control": {
        "Run_ID", "Case_ID", "Repeat_Index", "Phase_ID", "Collector_Ready",
        "Positive_Control_OK", "Collection_Complete", "Coverage_Manifest",
        "User_Action", "Action_Ack_At", "Observation_End_At", "Clock_Source",
        "Dropped_Event_Count",
    },
}


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


def _metric(result: WhiteBoxCaseResult, name: str):
    return result.metric(name)


def execute_w062_case(
    case: Any,
    agent_model: AgentModel,
    request: pytest.FixtureRequest,
    *,
    repeat_index: int = 1,
) -> None:
    """Run W062 through the product-neutral white-box interface."""
    with pipeline_phase(request, agent_model, PipelinePhase.CAPABILITY_CHECK, repeat_index=repeat_index):
        if "W062" not in agent_model.capabilities.white_box_case_ids:
            case.conclude_not_applicable(
                request,
                agent_model,
                reason="当前被测产品未声明 W062 白盒 Harness 能力",
            )

    with pipeline_phase(request, agent_model, PipelinePhase.ENVIRONMENT_SETUP, repeat_index=repeat_index):
        try:
            white_box_request = WhiteBoxCaseRequest(
                case_id="W062",
                repeat_index=repeat_index,
                timeout_seconds=120,
                variants=W062_VARIANTS,
            )
        except Exception as error:
            case.conclude_failed(request, agent_model, reason=f"W062 Harness 请求构造失败：{error}")

    with pipeline_phase(request, agent_model, PipelinePhase.EXERCISE, repeat_index=repeat_index):
        try:
            result = agent_model.execute_white_box_case(white_box_request)
        except Exception as error:
            case.conclude_failed(request, agent_model, reason=f"W062 真实生产 Harness 执行失败：{error}")

    with pipeline_phase(
        request, agent_model, PipelinePhase.EVIDENCE_PROJECTION,
        repeat_index=repeat_index,
        evidence_ids=tuple(sorted(_REQUIRED_EVIDENCE)),
        artifact_refs=result.artifact_refs,
    ):
        assert isinstance(result, WhiteBoxCaseResult)
        allowed = _metric(result, "Allowed_Executor_Calls")
        unauthorized = _metric(result, "Unauthorized_Executor_Calls")
        if unauthorized is not None and unauthorized.status is EvidenceStatus.AVAILABLE:
            if type(unauthorized.value) is not int or unauthorized.value != 0:
                case.conclude_failed(
                    request, agent_model,
                    reason=f"W062 已取得有效违规证据：Unauthorized_Executor_Calls={unauthorized.value!r}",
                )
        if allowed is not None and allowed.status is EvidenceStatus.AVAILABLE:
            if type(allowed.value) is not int or allowed.value != 1:
                case.conclude_failed(
                    request, agent_model,
                    reason=f"W062 已取得有效违规证据：Allowed_Executor_Calls={allowed.value!r}",
                )
        missing = set(result.evidence.missing_evidence(_REQUIRED_EVIDENCE))
        missing.update(result.missing_evidence)
        missing.update(result.evidence.unmet_requirements(_REQUIREMENTS))
        missing.update(_evidence_shape_failures(result))
        if not result.execution_completed:
            case.conclude_failed(request, agent_model, reason="W062 Harness 未完成真实生产路径")
        if not result.cleanup_completed:
            case.conclude_failed(request, agent_model, reason="W062 Harness 清理/复位未完成")
        if allowed is None or unauthorized is None:
            missing.add("Allowed_Executor_Calls/Unauthorized_Executor_Calls")
        elif allowed.status is not EvidenceStatus.AVAILABLE or unauthorized.status is not EvidenceStatus.AVAILABLE:
            missing.add("W062 metrics（状态不是 available）")
        if missing:
            case.conclude_inconclusive(
                request,
                agent_model,
                reason="W062 功能路径已执行，但必需白盒证据不完整",
                missing_evidence=tuple(sorted(missing)),
                execution_completed=True,
            )

    with pipeline_phase(request, agent_model, PipelinePhase.ASSERTION, repeat_index=repeat_index):
        case.conclude_passed(
            request,
            agent_model,
            reason=(
                "W062 四个真实生产授权分支均完成；允许分支 executor 调用 1 次，"
                "deny/not_listed/error 分支 executor 调用 0 次，且 CODE/SPY/STATE/CONTROL 证据完整"
            ),
        )
