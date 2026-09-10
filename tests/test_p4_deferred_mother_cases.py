"""Verify P4 deferred mother cases never contact the tested Agent."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.mother_cases import p4_deferred
from test_cases.mother_cases.p4_deferred import (
    P4_DEFERRED_PROFILES,
    P4DeferredMotherCaseRunner,
    p4_deferred_profile,
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
        raise AssertionError("P4 deferred cases must not authenticate")

    def send_prompt(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P4 deferred cases must not send prompts")

    def configure_mock_tool(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P4 deferred cases must not configure mock tools")

    def configure_mock_tools(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("P4 deferred cases must not configure mock tools")


def _request() -> SimpleNamespace:
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "source_case_id": "TC-P4-DEFERRED",
        "priority": "P4",
        "category": "H",
        "arrangement": "排除-UI设备",
        "implementation_mode": "deferred",
        "required_capability": "device_ui：需要真实设备和 UI 观察。",
        "preconditions": (
            "【本轮安排】排除-UI设备。\n"
            "【重新纳入条件】真实设备、UI 操作和系统权限记录。"
        ),
        "uncovered_requirements": "端侧操作、设备状态和 UI 证据仍未覆盖。",
    }
    case.update(overrides)
    return case


def _run(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    *,
    profile: str,
) -> tuple[AssessmentOutcomeSignal, _Model, SimpleNamespace]:
    monkeypatch.setattr(p4_deferred, "mother_case_record", lambda _case_id: case)
    model = _Model()
    request = _request()
    with pytest.raises(AssessmentOutcomeSignal) as outcome:
        P4DeferredMotherCaseRunner().run_p4_deferred_case(
            source_case_id=str(case["source_case_id"]),
            profile=profile,
            agent_model=model,  # type: ignore[arg-type]
            request=request,  # type: ignore[arg-type]
        )
    return outcome.value, model, request


def test_profiles_cover_every_manifest_p4_capability_family() -> None:
    cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    actual = {
        str(case["required_capability"]).split("：", maxsplit=1)[0].strip()
        for case in cases
        if case["priority"] == "P4"
    }

    assert actual == P4_DEFERRED_PROFILES


def test_runner_api_has_no_judge_or_execution_fixture() -> None:
    parameters = inspect.signature(
        P4DeferredMotherCaseRunner.run_p4_deferred_case
    ).parameters

    assert "judge_model" not in parameters
    assert "repeat_index" not in parameters


@pytest.mark.parametrize("profile", sorted(P4_DEFERRED_PROFILES))
def test_each_profile_concludes_not_applicable_without_agent_interaction(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
) -> None:
    case = _case(required_capability=f"{profile}：真实设备公开入口和证据。")

    outcome, model, request = _run(monkeypatch, case, profile=profile)

    assert outcome.verdict.status is AssessmentStatus.NOT_APPLICABLE
    assert "本轮 CLI/设备评测范围不覆盖" in outcome.verdict.reason
    assert "不代表原条款或产品整体不适用" in outcome.verdict.reason
    assert request.node.user_properties[0][1] == "不适用"
    deferred_event = model.environment.ledger.events[0]
    assert deferred_event[0:2] == ("pytest", "p4_mother_case_deferred")
    assert deferred_event[2] == {
        "source_case_id": "TC-P4-DEFERRED",
        "priority": "P4",
        "category": "H",
        "arrangement": "排除-UI设备",
        "implementation_mode": "deferred",
        "profile": profile,
        "required_capability": f"{profile}：真实设备公开入口和证据。",
        "reentry_condition": "真实设备、UI 操作和系统权限记录。",
        "coverage_gap": "端侧操作、设备状态和 UI 证据仍未覆盖。",
    }
    assert model.environment.ledger.events[1][0:2] == (
        "assertion",
        "assessment_concluded",
    )


@pytest.mark.parametrize(
    ("overrides", "profile", "message"),
    (
        ({"source_case_id": "TC-OTHER"}, "device_ui", "与 manifest 记录"),
        ({"priority": "P3"}, "device_ui", "不是 P4"),
        ({"category": "E"}, "device_ui", "不是 H 类"),
        ({"arrangement": "暂缓-过程取证"}, "device_ui", "执行安排应为"),
        ({"implementation_mode": "pending"}, "device_ui", "必须为 deferred"),
        (
            {"required_capability": "unknown：尚无入口。"},
            "unknown",
            "没有明确的 P4 排除 profile",
        ),
        ({}, "risk_action", "profile 应为 device_ui"),
        ({"preconditions": "没有重新纳入标记"}, "device_ui", "缺少重新纳入条件"),
        (
            {"preconditions": "【重新纳入条件】  "},
            "device_ui",
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
    monkeypatch.setattr(p4_deferred, "mother_case_record", lambda _case_id: case)
    model = _Model()

    with pytest.raises(ValueError, match=message):
        P4DeferredMotherCaseRunner().run_p4_deferred_case(
            source_case_id="TC-P4-DEFERRED",
            profile=profile,
            agent_model=model,  # type: ignore[arg-type]
            request=_request(),  # type: ignore[arg-type]
        )

    assert model.environment.ledger.events == []


def test_profile_resolution_uses_required_capability_prefix() -> None:
    assert p4_deferred_profile(_case()) == "device_ui"
    with pytest.raises(ValueError, match="没有明确的 P4 排除 profile"):
        p4_deferred_profile(
            _case(required_capability="unsupported：不受支持的真实接口。")
        )
