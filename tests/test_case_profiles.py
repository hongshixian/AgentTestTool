"""Test case classification derived from specifications."""

from test_cases.black_box.profiles import DIRECT_WORKSPACE_CASES, FRAMEWORK_METRICS, profile_for
from test_cases.black_box.specs import load_black_box_specs


def test_every_case_has_a_profile():
    specs = load_black_box_specs()
    profiles = {case_id: profile_for(spec) for case_id, spec in specs.items()}
    assert len(profiles) == 334
    assert all(p.handler in {
        "state", "generic_result", "file_boundary", "output_channel",
        "decode_boundary", "expiry", "document_boundary",
        "t001", "t002_t004", "t011_calendar", "t016", "t102",
    } for p in profiles.values())


def test_direct_workspace_cases_get_no_tool():
    specs = load_black_box_specs()
    for case_id in DIRECT_WORKSPACE_CASES:
        p = profile_for(specs[case_id])
        assert not p.has_submission_tool, f"{case_id} works in workspace so must not have tool"


def test_framework_metrics_never_appear_in_submission():
    specs = load_black_box_specs()
    for case_id, spec in specs.items():
        p = profile_for(spec)
        overlap = set(p.submission_metrics) & FRAMEWORK_METRICS
        assert not overlap, f"{case_id} submits {overlap} which framework computes"


def test_representative_cases():
    specs = load_black_box_specs()
    assert profile_for(specs["B005"]).handler == "file_boundary"
    assert profile_for(specs["B006"]).handler == "output_channel"
    assert profile_for(specs["B009"]).handler == "expiry"
    assert profile_for(specs["B029"]).handler == "decode_boundary"
    assert profile_for(specs["B042"]).handler == "document_boundary"
    assert profile_for(specs["T001"]).handler == "t001"
    assert profile_for(specs["T011"]).handler == "t011_calendar"
    assert profile_for(specs["T016"]).handler == "t016"
    assert profile_for(specs["T102"]).handler == "t102"
    # Generic handlers
    assert profile_for(specs["T017"]).handler == "generic_result"
    assert profile_for(specs["T005"]).handler == "state"
