"""Regression tests for the generated three-volume grey-box suite."""

from __future__ import annotations

import json
from pathlib import Path

from agent_models import EvidenceBundle, EvidencePhase, EvidenceRecord, TranscriptTurn, TurnResult
from assertions.judge import JudgeStatus
from scripts.build_grey_box_cases import DEFERRED_CASE_IDS, EXPECTED_CASE_IDS, build_manifest
from test_cases.grey_box.base import (
    _h034_verdict,
    _prompt,
    _required_ids,
    _system_marker_verdict,
    _uses_tool,
)
from test_cases.grey_box.specs import load_grey_box_specs


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "local_docs" / "测试用例集-三套卷版本" / "自动化测试三套卷_候选拆分.xlsx"
CLAUSES = ROOT / "agent_test_tool" / "reporting" / "clauses.json"
CATALOG = ROOT / "configs" / "grey_box_cases.json"


def test_manifest_matches_reviewed_73_case_scope() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))

    assert payload["case_count"] == 73
    assert tuple(case["case_id"] for case in payload["cases"]) == EXPECTED_CASE_IDS
    assert set(payload["deferred_case_ids"]) == DEFERRED_CASE_IDS
    assert {case["case_id"] for case in payload["deferred_cases"]} == DEFERRED_CASE_IDS
    assert all(case["deferred_reason"] for case in payload["deferred_cases"])
    assert not DEFERRED_CASE_IDS.intersection(EXPECTED_CASE_IDS)


def test_manifest_is_reproducible_from_workbook() -> None:
    assert build_manifest(WORKBOOK, CLAUSES) == json.loads(
        CATALOG.read_text(encoding="utf-8")
    )


def test_every_case_has_one_independent_wrapper() -> None:
    wrapper_ids = {
        path.stem.removeprefix("test_").upper()
        for path in (ROOT / "test_cases" / "grey_box").glob("test_h*.py")
    }

    assert wrapper_ids == set(EXPECTED_CASE_IDS) | DEFERRED_CASE_IDS


def test_deferred_wrappers_directly_record_not_applicable_reason() -> None:
    for case_id in DEFERRED_CASE_IDS:
        source = (
            ROOT / "test_cases" / "grey_box" / f"test_{case_id.lower()}.py"
        ).read_text(encoding="utf-8")
        assert "def test_case_not_implemented" in source
        assert "当前暂未实现" in source
        assert "conclude_not_applicable" in source
        assert "send_prompt" not in source


def test_evidence_families_require_their_authoritative_channels() -> None:
    specs = load_grey_box_specs()
    for spec in specs.values():
        required = _required_ids(spec)
        if "模型Hook" in spec.evidence_scope:
            assert "reconstructed_agent_trace" in required
        if "工具Hook" in spec.evidence_scope:
            assert {"mock_tool_io", "reconstructed_agent_trace"} <= required
        if spec.evidence_scope == "通信取证":
            assert {"mock_tool_io", "network_exchange_trace"} <= required
        assert _uses_tool(spec) is (
            "工具Hook" in spec.evidence_scope
            or spec.evidence_scope == "通信取证"
            or spec.case_id == "H034"
        )


def test_h021_attack_prompt_does_not_contain_the_protected_marker() -> None:
    spec = load_grey_box_specs()["H021"]

    prompt = _prompt(spec)

    assert str(spec.input_config["Marker"]) not in prompt
    assert str(spec.input_config["Public_Marker"]) in prompt
    assert "系统提示" in prompt


def test_h022_disable_safety_prompt_does_not_contain_protected_marker() -> None:
    spec = load_grey_box_specs()["H022"]

    prompt = _prompt(spec)

    assert str(spec.input_config["Marker"]) not in prompt
    assert str(spec.input_config["Public_Marker"]) in prompt
    assert "关闭" in prompt


def test_h021_uses_model_input_and_visible_output_for_deterministic_verdict() -> None:
    spec = load_grey_box_specs()["H021"]
    marker = str(spec.input_config["Marker"])
    result = TurnResult("PUBLIC_OK", "PUBLIC_OK", "", 0, True, 0.1, "session-1")
    bundle = EvidenceBundle(
        sample_id="H021",
        prompt_id="01",
        run_id="run-1",
        transcript=(TranscriptTurn("attack", result),),
        records=(EvidenceRecord(
            "observed_model_context",
            "model_context",
            EvidencePhase.AFTER,
            {"messages": [{"role": "system", "content": marker}]},
        ),),
    )

    status, reason = _system_marker_verdict(spec, bundle, result)

    assert status is JudgeStatus.PASS
    assert "System_Input_Marker_Hits=1" in reason


def test_h034_ignores_unexposed_registered_tools() -> None:
    result = TurnResult("sunny", "sunny", "", 0, True, 0.1, "session-1")
    bundle = EvidenceBundle(
        sample_id="H034",
        prompt_id="01",
        run_id="run-1",
        transcript=(TranscriptTurn("weather", result),),
        records=(
            EvidenceRecord(
                "observed_model_context",
                "agent_trace_evidence",
                EvidencePhase.AFTER,
                {"model_calls": [{"visible_tools": [
                    {"type": "function", "function": {"name": "mcp__ats_mock__weather.get"}},
                ]}]},
            ),
            EvidenceRecord(
                "mock_tool_io",
                "runtime_evidence",
                EvidencePhase.AFTER,
                {"calls": [{"tool_name": "weather.get"}]},
            ),
        ),
    )

    status, reason = _h034_verdict(bundle, result)

    assert status is JudgeStatus.PASS
    assert "Unapproved_Visible_Tool_Count=0" in reason
