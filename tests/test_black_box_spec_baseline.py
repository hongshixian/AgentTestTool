"""Behaviour baseline for every black-box case specification.

The refactor must not change what any case *means*. These tests pin the
semantic content of all 334 catalog entries so a structural change that
accidentally alters a prompt, a rule, or a fixture fails immediately.

The snapshot is keyed by field values, never by class or module names, so
renaming a type during the refactor is not a baseline change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_cases.black_box.models import BlackBoxCaseSpec
from test_cases.black_box.specs import load_black_box_specs

BASELINE = Path(__file__).with_name("fixtures") / "black_box_spec_baseline.json"


def semantic_view(spec: BlackBoxCaseSpec) -> dict:
    """Return only the fields that define case behaviour.

    ``metadata`` is included because handlers read ``input_config`` from it,
    but ``Expected_Observations`` / ``Fixture_Health_Check`` /
    ``Adapter_Case_Handler`` are internal bookkeeping that may legitimately
    move out of metadata during the refactor, so they are dropped.
    """
    metadata = {
        key: value
        for key, value in dict(spec.metadata).items()
        if key not in {"Expected_Observations", "Fixture_Health_Check", "Adapter_Case_Handler"}
    }
    criterion = spec.judge_criterion
    return {
        "case_id": spec.case_id,
        "title": spec.title,
        "repeat_count": spec.repeat_count,
        "timeout_seconds": spec.timeout_seconds,
        "steps": [
            {
                "phase_id": step.phase_id,
                "prompt": step.prompt,
                "allow_tools": step.allow_tools,
                "permission_policy": step.permission_policy,
            }
            for step in spec.steps
        ],
        "workspace_files": [
            {"path": item.path, "content": item.content, "asset": item.asset, "mode": item.mode}
            for item in spec.workspace_files
        ],
        "initial_business_state": dict(spec.initial_business_state),
        "assertion_rules": [
            {"metric": rule.metric, "operator": rule.operator, "expected": rule.expected}
            for rule in spec.assertion_rules
        ],
        "judge_criterion": None if criterion is None else {
            "case_id": criterion.case_id,
            "title": criterion.title,
            "description": criterion.description,
            "pass_criteria": criterion.pass_criteria,
            "fail_criteria": criterion.fail_criteria,
            "required_evidence": list(criterion.required_evidence),
            "checkpoints": list(criterion.checkpoints),
        },
        "marker": spec.marker,
        "public_marker": spec.public_marker,
        "metadata": metadata,
    }


def current_view() -> dict[str, dict]:
    return {case_id: semantic_view(spec) for case_id, spec in sorted(load_black_box_specs().items())}


def test_every_catalog_case_matches_the_behaviour_baseline() -> None:
    assert BASELINE.is_file(), f"missing baseline snapshot: {BASELINE}"
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(current_view(), ensure_ascii=False))

    assert set(actual) == set(expected), (
        f"case set changed: missing={sorted(set(expected) - set(actual))}, "
        f"added={sorted(set(actual) - set(expected))}"
    )
    drifted = [case_id for case_id in expected if actual[case_id] != expected[case_id]]
    assert not drifted, f"case semantics changed for: {', '.join(drifted)}"


def test_baseline_covers_both_batches() -> None:
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert len(expected) == 334
    assert sum(1 for case_id in expected if case_id.startswith("B")) == 42
    assert sum(1 for case_id in expected if case_id.startswith("T")) == 292


@pytest.mark.parametrize("case_id", ["B005", "B009", "T001", "T036", "T278"])
def test_representative_cases_have_expected_shape(case_id: str) -> None:
    """Spot-check the cases whose handlers exercise the widest feature set."""
    view = current_view()[case_id]
    assert view["steps"], f"{case_id} must declare at least one step"
    assert view["assertion_rules"], f"{case_id} must declare assertion rules"
