"""Verify P3 deferred mother cases never contact the tested Agent."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.mother_cases import p3_deferred
from test_cases.mother_cases.p3_deferred import (
    P3_DEFERRED_PROFILE_BY_REQUIREMENT,
    P3DeferredMotherCaseRunner,
    p3_deferred_profile,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "mother_cases_v3.json"


class _Ledger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def record(self, source: str, kind: str, data: dict[str, object]) -> None:
        self.events.append((source, kind, data))


class _Model:
    def __init__(self) -> None:
        self.environment = SimpleNamespace(ledger=_Ledger())

    def check_authentication(self) -> None:
        raise AssertionError("P3 deferred cases must not authenticate")

    def send_prompt(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P3 deferred cases must not send prompts")

    def configure_mock_tool(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P3 deferred cases must not configure mock tools")

    def configure_mock_tools(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P3 deferred cases must not configure mock tools")


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "source_case_id": "TC-P3-DEFERRED",
        "priority": "P3",
        "category": "E",
        "arrangement": "暂缓-过程取证",
        "implementation_mode": "deferred",
        "required_capability": "product_audit：需要产品原生日志查询入口。",
        "preconditions": (
            "【本轮安排】暂缓-过程取证。\n"
            "【重新纳入条件】产品原生日志查询和导出入口。"
        ),
        "uncovered_requirements": "产品原生过程记录与可核验字段仍未覆盖。",
    }
    case.update(overrides)
    return case


def _run(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    *,
    profile: str,
) -> tuple[AssessmentOutcomeSignal, _Model, SimpleNamespace]:
    monkeypatch.setattr(p3_deferred, "mother_case_record", lambda _case_id: case)
    model = _Model()
    request = _request()
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        P3DeferredMotherCaseRunner().run_p3_deferred_case(
            source_case_id=str(case["source_case_id"]),
            profile=profile,
            agent_model=model,  # type: ignore[arg-type]
            request=request,  # type: ignore[arg-type]
        )
    return outcome.value, model, request


def test_profile_map_covers_every_p3_e_f_capability_family() -> None:
    cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    actual = {
        (case["category"], str(case["required_capability"]).split("：", 1)[0])
        for case in cases
        if case["priority"] == "P3" and case["category"] in {"E", "F"}
    }

    assert actual == set(P3_DEFERRED_PROFILE_BY_REQUIREMENT)
    assert set(P3_DEFERRED_PROFILE_BY_REQUIREMENT.values()) == {
        "instance_api",
        "product_audit",
        "material",
        "component_loader",
        "extension_loader",
        "device_ui",
        "route_observation",
        "risk_action",
    }


def test_runner_api_has_no_judge_or_execution_fixture() -> None:
    parameters = inspect.signature(
        P3DeferredMotherCaseRunner.run_p3_deferred_case
    ).parameters

    assert "judge_model" not in parameters
    assert "repeat_index" not in parameters


@pytest.mark.parametrize(
    ("category", "capability", "profile"),
    tuple(
        (category, capability, profile)
        for (category, capability), profile in sorted(
            P3_DEFERRED_PROFILE_BY_REQUIREMENT.items()
        )
    ),
)
def test_each_profile_concludes_not_applicable_without_agent_interaction(
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    capability: str,
    profile: str,
) -> None:
    arrangement = "暂缓-过程取证" if category == "E" else "暂缓-材料规则"
    case = _case(
        category=category,
        arrangement=arrangement,
        required_capability=f"{capability}：真实公开入口和证据。",
    )

    outcome, model, request = _run(monkeypatch, case, profile=profile)

    assert outcome.verdict.status is AssessmentStatus.NOT_APPLICABLE
    assert "本轮评测环境" in outcome.verdict.reason
    assert "不代表原条款或产品整体不适用" in outcome.verdict.reason
    assert request.node.user_properties[0][1] == "不适用"
    deferred_event = model.environment.ledger.events[0]
    assert deferred_event[0:2] == ("pytest", "p3_mother_case_deferred")
    assert deferred_event[2] == {
        "source_case_id": "TC-P3-DEFERRED",
        "priority": "P3",
        "category": category,
        "arrangement": arrangement,
        "implementation_mode": "deferred",
        "profile": profile,
        "required_capability": f"{capability}：真实公开入口和证据。",
        "reentry_condition": "产品原生日志查询和导出入口。",
        "coverage_gap": "产品原生过程记录与可核验字段仍未覆盖。",
    }
    assert model.environment.ledger.events[1][0:2] == (
        "assertion",
        "assessment_concluded",
    )


@pytest.mark.parametrize(
    ("overrides", "profile", "message"),
    (
        ({"source_case_id": "TC-OTHER"}, "product_audit", "与 manifest 记录"),
        ({"priority": "P2"}, "product_audit", "不是 P3"),
        ({"category": "G"}, "product_audit", "不是 E/F"),
        ({"arrangement": "暂缓-材料规则"}, "product_audit", "执行安排应为"),
        ({"implementation_mode": "pending"}, "product_audit", "必须为 deferred"),
        (
            {"required_capability": "unknown：尚无入口。"},
            "unknown",
            "没有明确的 P3 暂缓 profile",
        ),
        ({}, "material", "profile 应为 product_audit"),
        ({"preconditions": "没有重新纳入标记"}, "product_audit", "缺少重新纳入条件"),
        (
            {"preconditions": "【重新纳入条件】  "},
            "product_audit",
            "重新纳入条件为空",
        ),
    ),
)
def test_runner_rejects_invalid_deferred_metadata(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    profile: str,
    message: str,
) -> None:
    case = _case(**overrides)
    monkeypatch.setattr(p3_deferred, "mother_case_record", lambda _case_id: case)
    model = _Model()

    with pytest.raises(ValueError, match=message):
        P3DeferredMotherCaseRunner().run_p3_deferred_case(
            source_case_id="TC-P3-DEFERRED",
            profile=profile,
            agent_model=model,  # type: ignore[arg-type]
            request=_request(),  # type: ignore[arg-type]
        )

    assert model.environment.ledger.events == []


def test_profile_resolution_requires_category_and_capability_pair() -> None:
    assert p3_deferred_profile(_case()) == "product_audit"
    with pytest.raises(ValueError, match="没有明确的 P3 暂缓 profile"):
        p3_deferred_profile(_case(category="F"))
