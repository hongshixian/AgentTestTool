"""Route P2 B/C mother cases to public proxy experiments or explicit N/A."""

from __future__ import annotations

from typing import Any

import pytest

from agent_models import AgentModel
from assertions.judge import OpenAICompatibleJudge
from test_cases.mother_cases.p2_proxy import (
    P2_BC_PROFILE_BY_SOURCE_CASE,
    P2ProxyMotherCaseRunner,
)
from test_cases.mother_cases.relaxed import mother_case_record


def _text(case: dict[str, Any], field: str) -> str:
    value = str(case.get(field) or "").strip()
    if not value:
        raise ValueError(f"{case.get('source_case_id')} 缺少 {field}")
    return value


def required_capability_key(case: dict[str, Any]) -> str:
    """Return the stable capability prefix from the workbook requirement."""

    return _text(case, "required_capability").split("：", maxsplit=1)[0].strip()


class P2IdentityMotherCaseRunner(P2ProxyMotherCaseRunner):
    """Preserve child traceability while executing the audited P2 B/C profile."""

    def run_p2_bc_case(
        self,
        *,
        source_case_id: str,
        representative_child_id: str,
        representative_child_script: str,
        agent_model: AgentModel,
        judge_model: OpenAICompatibleJudge | None,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        case = dict(mother_case_record(source_case_id))
        if _text(case, "priority") != "P2" or _text(case, "category") not in {
            "B",
            "C",
        }:
            raise ValueError(f"{source_case_id} 不是 P2 B/C 母用例")

        candidates = {
            (str(item.get("case_id") or ""), str(item.get("script") or ""))
            for item in case.get("representative_child_candidates", ())
            if isinstance(item, dict)
        }
        selected = (representative_child_id, representative_child_script)
        if selected not in candidates:
            raise ValueError(
                f"{source_case_id} 的代表子用例不在 manifest 候选集中："
                f"{representative_child_id}"
            )

        del judge_model, repeat_index
        capability_key = required_capability_key(case)
        profile = P2_BC_PROFILE_BY_SOURCE_CASE.get(source_case_id)
        agent_model.environment.ledger.record(
            "pytest",
            "p2_mother_case_profile_selected",
            {
                "source_case_id": source_case_id,
                "category": _text(case, "category"),
                "required_capability": capability_key,
                "representative_child_id": representative_child_id,
                "representative_child_script": representative_child_script,
                "execution_mode": (
                    f"p2_proxy:{profile}" if profile is not None else "not_applicable"
                ),
            },
        )
        if profile is None:
            self.conclude_not_applicable(
                request,
                agent_model,
                reason=(
                    f"统一 AgentModel 尚无“{capability_key}”所需的真实公共接口；"
                    "不使用模型自述、普通文件或测试自设状态冒充产品能力。"
                    f"代表来源保留为 {representative_child_id}。"
                ),
            )

        P2ProxyMotherCaseRunner.run_p2_proxy_case(
            self,
            source_case_id=source_case_id,
            profile=profile,
            agent_model=agent_model,
            request=request,
        )
