"""Case classification derived once from a case specification.

Three different modules used to answer "which kind of case is this, and how
does it run" with their own hard-coded frozensets: ``environment.py`` decided
whether to expose a submission tool, and ``scenario_handlers.py`` decided
which handler to dispatch to. Both answers derive from the same facts, so
they are computed together here and read from one place.

This module owns *classification only*. It never imports the environment
builder or the handlers, so it stays importable from either side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from test_cases.black_box.models import AssertionRule, BlackBoxCaseSpec

HandlerName = Literal[
    "state",
    "generic_result",
    "file_boundary",
    "output_channel",
    "decode_boundary",
    "expiry",
    "document_boundary",
    "t001",
    "t002_t004",
    "t011_calendar",
    "t016",
    "t102",
]

# Metrics the framework computes itself from responses or workspace files.
# They never appear in the submission tool schema: an agent cannot report a
# value the framework means to measure independently.
FRAMEWORK_METRICS = frozenset({
    "Positive_Output_Marker_Hits", "Forbidden_Marker_Hits",
    "Decoded_Forbidden_Marker_Hits", "Positive_Decode_Marker_Hits",
    "Other_User_Marker_Hits", "Protected_Marker_Hits",
    "Deleted_Marker_Hits", "After_Clear_Marker_Hits",
    "B_Read_Marker_Hits",
    "forbidden_value_hits", "forbidden_values",
    "body_sha256",
    "Valid_Window_File_Changes", "After_Expiry_File_Changes",
    "After_Revoke_File_Changes",
    "input_unchanged", "inputs_unchanged",
    "Completed_Count", "Nonzero_Returncode_Count", "Workspace_Change_Count",
})

# Cases handled by a dedicated scenario module rather than the generic ones.
_HANDLER_BY_CASE: dict[str, HandlerName] = {}
for _case_id in (f"B{index:03d}" for index in range(1, 43)):
    if _case_id == "B009":
        _HANDLER_BY_CASE[_case_id] = "expiry"
    elif _case_id in {"B005", "B007", "B008", "B025", "B026", "B027", "B030"}:
        _HANDLER_BY_CASE[_case_id] = "file_boundary"
    elif _case_id in {"B006", "B028", "B034", "B035", "B036", "B037"}:
        _HANDLER_BY_CASE[_case_id] = "output_channel"
    elif _case_id in {"B029", "B038", "B039", "B040", "B041"}:
        _HANDLER_BY_CASE[_case_id] = "decode_boundary"
    elif _case_id == "B042":
        _HANDLER_BY_CASE[_case_id] = "document_boundary"
# B001-B004, B011-B024, B031-B033 use the generic handlers selected below.

_HANDLER_BY_CASE.update({
    "T001": "t001", "T002": "t002_t004", "T003": "t002_t004", "T004": "t002_t004",
    "T011": "t011_calendar", "T016": "t016", "T102": "t102",
})

# Cases whose metrics are submitted through the tool rather than derived.
_GENERIC_RESULT_CASES = frozenset({
    "T017", "T018", "T026", "T027", "T028", "T029", "T030", "T031", "T032", "T033",
    "T034", "T035", "T052", "T053", "T054", "T055", "T056", "T057", "T058", "T059",
    "T072", "T073", "T074", "T075", "T081", "T082", "T083", "T090", "T091", "T092",
    "T093", "T094", "T095", "T096", "T097", "T098", "T099", "T100", "T101", "T103",
    "T104", "T105", "T106", "T107", "T108", "T109", "T110", "T111", "T112", "T113",
    "T114", "T115", "T134", "T135", "T136", "T137", "T138", "T139", "T140", "T141",
    "T142", "T143", "T144", "T145", "T146", "T147", "T148", "T149", "T150", "T151",
    "T188", "T189", "T190", "T191", "T208", "T209", "T210", "T211", "T216", "T217",
    "T218", "T219", "T220", "T221", "T222", "T223", "T224", "T225", "T226", "T227",
    "T228", "T229", "T230", "T231", "T232", "T233", "T234", "T235", "T236", "T237",
    "T238", "T239", "T240", "T241", "T242", "T243", "T244", "T245", "T246", "T247",
    "T248", "T249", "T250", "T251", "T252", "T253", "T254", "T255", "T256", "T257",
    "T258", "T259", "T260", "T261", "T262", "T263", "T264", "T265", "T266", "T267",
    "T268", "T269", "T270", "T271", "T272", "T273", "T274", "T275", "T276", "T277",
    "T278", "T279", "T280", "T281", "T282", "T283", "T284", "T285", "T286",
})

# Cases whose workspace fixtures are written by the case itself rather than
# declared in the catalog. They must keep doing so until their fixtures move
# into the catalog, which is a separate, behaviour-changing step.
SELF_PREPARED_CASES = frozenset({
    "B006", "B009", "B028", "B029", "B034", "B035", "B036", "B037",
    "B038", "B039", "B040", "B041", "B042",
})

# Cases that do their work directly in the workspace. They never receive a
# submission tool: what they report is read from files, not from a call.
DIRECT_WORKSPACE_CASES = frozenset({
    "B005", "B006", "B007", "B008", "B009", "B025", "B026", "B027",
    "B028", "B029", "B030", "B034", "B035", "B036", "B037", "B038",
    "B039", "B040", "B041", "B042", "T001", "T002", "T003", "T004", "T016", "T102",
    "T026", "T027", "T028", "T029", "T030", "T031", "T032",
})


@dataclass(frozen=True, slots=True)
class CaseProfile:
    """What kind of case this is and how it should be run."""

    handler: HandlerName
    has_submission_tool: bool
    submission_metrics: tuple[str, ...]
    framework_metrics: frozenset[str]
    prepares_own_files: bool

    @property
    def is_text_only(self) -> bool:
        return self.handler == "state" and not self.has_submission_tool


def _non_text_rules(spec: BlackBoxCaseSpec) -> tuple[AssertionRule, ...]:
    return tuple(
        rule for rule in spec.assertion_rules
        if rule.metric != "expected_result" and rule.metric not in FRAMEWORK_METRICS
    )


def profile_for(spec: BlackBoxCaseSpec) -> CaseProfile:
    """Classify one case. Pure: depends only on the specification."""
    handler = _HANDLER_BY_CASE.get(spec.case_id)
    if handler is None:
        handler = "generic_result" if spec.case_id in _GENERIC_RESULT_CASES else "state"
    rules = _non_text_rules(spec)
    return CaseProfile(
        handler=handler,
        # A case that works directly in the workspace reports through files,
        # so it gets no tool even when it declares structured metrics.
        has_submission_tool=bool(rules) and spec.case_id not in DIRECT_WORKSPACE_CASES,
        submission_metrics=tuple(rule.metric for rule in rules),
        framework_metrics=FRAMEWORK_METRICS,
        prepares_own_files=spec.case_id in SELF_PREPARED_CASES,
    )


def profiles_for_all(specs: dict[str, BlackBoxCaseSpec]) -> dict[str, CaseProfile]:
    return {case_id: profile_for(spec) for case_id, spec in specs.items()}
