"""Route P4 device- and UI-excluded mother cases explicitly."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from agent_models import AgentModel
from test_cases.mother_cases.base import MotherCaseScenarioRunner
from test_cases.mother_cases.relaxed import mother_case_record


P4_DEFERRED_PROFILES = frozenset(
    {
        "files_and_sink",
        "device_ui",
        "risk_notice",
        "risk_action",
        "cancel_task",
    }
)

_REENTRY_MARKER = "【重新纳入条件】"


def _text(case: Mapping[str, Any], field: str) -> str:
    value = str(case.get(field) or "").strip()
    if not value:
        raise ValueError(f"{case.get('source_case_id')} 缺少 {field}")
    return value


def required_capability_key(case: Mapping[str, Any]) -> str:
    """Return the stable capability prefix from a workbook requirement."""

    return _text(case, "required_capability").split("：", maxsplit=1)[0].strip()


def p4_deferred_profile(case: Mapping[str, Any]) -> str:
    """Resolve a supported P4 profile from its required capability."""

    profile = required_capability_key(case)
    if profile not in P4_DEFERRED_PROFILES:
        raise ValueError(
            f"{case.get('source_case_id')} 没有明确的 P4 排除 profile：{profile}"
        )
    return profile


def _reentry_condition(case: Mapping[str, Any]) -> str:
    preconditions = _text(case, "preconditions")
    marker_index = preconditions.find(_REENTRY_MARKER)
    if marker_index < 0:
        raise ValueError(
            f"{case.get('source_case_id')} 的 preconditions 缺少重新纳入条件"
        )
    condition = preconditions[marker_index + len(_REENTRY_MARKER) :].strip()
    if not condition:
        raise ValueError(f"{case.get('source_case_id')} 的重新纳入条件为空")
    return condition


class P4DeferredMotherCaseRunner(MotherCaseScenarioRunner):
    """Conclude a validated P4 excluded row without contacting the Agent."""

    def run_p4_deferred_case(
        self,
        *,
        source_case_id: str,
        profile: str,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        case = mother_case_record(source_case_id)
        manifest_source_case_id = _text(case, "source_case_id")
        priority = _text(case, "priority")
        category = _text(case, "category")
        arrangement = _text(case, "arrangement")
        implementation_mode = _text(case, "implementation_mode")

        if manifest_source_case_id != source_case_id:
            raise ValueError(
                f"请求的母用例 ID {source_case_id} 与 manifest 记录 "
                f"{manifest_source_case_id} 不一致"
            )
        if priority != "P4":
            raise ValueError(f"{source_case_id} 不是 P4 母用例")
        if category != "H":
            raise ValueError(f"{source_case_id} 不是 H 类排除母用例")
        if arrangement != "排除-UI设备":
            raise ValueError(
                f"{source_case_id} 的执行安排应为 排除-UI设备，实际为 {arrangement}"
            )
        if implementation_mode != "deferred":
            raise ValueError(
                f"{source_case_id} 的 implementation_mode 必须为 deferred，"
                f"实际为 {implementation_mode}"
            )

        expected_profile = p4_deferred_profile(case)
        if profile != expected_profile:
            raise ValueError(
                f"{source_case_id} 的 P4 排除 profile 应为 {expected_profile}，"
                f"实际为 {profile}"
            )

        required_capability = _text(case, "required_capability")
        reentry_condition = _reentry_condition(case)
        coverage_gap = _text(case, "uncovered_requirements")
        agent_model.environment.ledger.record(
            "pytest",
            "p4_mother_case_deferred",
            {
                "source_case_id": source_case_id,
                "priority": priority,
                "category": category,
                "arrangement": arrangement,
                "implementation_mode": implementation_mode,
                "profile": profile,
                "required_capability": required_capability,
                "reentry_condition": reentry_condition,
                "coverage_gap": coverage_gap,
            },
        )
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "本轮 CLI/设备评测范围不覆盖该用例，"
                f"按“{arrangement}”排除；重新纳入需要：{reentry_condition}。"
                "该结论仅表示本轮评测环境覆盖不足，"
                "不代表原条款或产品整体不适用。"
            ),
        )
