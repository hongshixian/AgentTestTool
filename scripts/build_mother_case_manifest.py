"""Build the checked-in mother-case manifest from the CLI v3 workbook."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import posixpath
import re
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile


SHEET_NAME = "01-用例总表"
EXPECTED_CASE_COUNT = 385
EXPECTED_PRIORITY_COUNTS = {"P1": 47, "P2": 242, "P3": 60, "P4": 36}
EXPECTED_P1_MODE_COUNTS = {
    "delegate": 12,
    "p1_output": 12,
    "p1_proxy": 11,
    "p1_state": 12,
}

# Curated from docs/p1_mother_case_inventory.md. Pending entries identify the
# intended path but cannot delegate until their child implementation is executable.
P1_REPRESENTATIVE_PATHS = {
    "TC-5.1d-D6-01": ("ATS-5.1d-D6-01-S01-01", "test_cases/test_traceability_evidence_validity.py", "pending"),
    "TC-5.2a-D1-01": ("ATS-5.2a-D1-01-S01-01", "test_cases/test_data_inventory_minimization_mechanism.py", "pending"),
    "TC-5.2a-D2-01": ("ATS-5.2a-D2-01-S01-02", "test_cases/test_local_calendar_data_minimization.py", "pending"),
    "TC-5.2a-D3-01": ("ATS-5.2a-D3-01-S01-01", "test_cases/test_cross_task_data_purpose_limitation.py", "pending"),
    "TC-5.2a-D5-01": ("ATS-5.2a-D5-01-S01-01", "test_cases/test_contact_scope_expansion.py", "pending"),
    "TC-5.2a-D6-01": ("ATS-5.2a-D6-01-S01-01", "test_cases/test_data_processing_trace_completeness.py", "pending"),
    "TC-5.2c-D3-01": ("ATS-5.2c-D3-01-S01-01", "test_cases/test_app_memory_deletion_autonomy_function_impact.py", "pending"),
    "TC-5.2d-D6-01": ("ATS-5.2d-D6-01-S01-01", "test_cases/test_cloud_upload_rejection_trace.py", "pending"),
    "TC-5.2e-D6-01": ("ATS-5.2e-D6-01-S01-01", "test_cases/test_consent_provision_withdrawal_log_reconciliation.py", "pending"),
    "TC-5.5c-D1-01": ("ATS-5.5c-D1-01-S01-01", "test_cases/test_log_at_rest_protection_credential_generation_and_privileged_boundary.py", "pending"),
    "TC-5.5c-D1-02": ("ATS-5.5c-D1-02-S01-01", "test_cases/test_primary_and_disaster_log_integrity_coverage.py", "pending"),
    "TC-5.5c-D2-02": ("ATS-5.5c-D2-02-S01-01", "test_cases/test_application_log_api_unauthorized_read_audit.py", "pending"),
    "TC-5.5c-D5-01": ("ATS-5.5c-D5-01-S01-01", "test_cases/test_log_integrity_subject_time_rehash.py", "pending"),
    "TC-5.5e-D2-01": ("ATS-5.5e-D2-01-S01-01", "test_cases/test_delivered_order_task_trace_reconstruction.py", "pending"),
    "TC-6.1b-D1-01": ("ATS-6.1b-D1-01-S01-01", "test_cases/test_forged_policy_deprecation_input_detection.py", "delegate"),
    "TC-6.1b-D1-02": ("ATS-6.1b-D1-02-S03-01", "test_cases/test_same_plaintext_user_dialog_input_detection.py", "delegate"),
    "TC-6.1b-D2-01": ("ATS-6.1b-D2-01-S01-02", "test_cases/test_plaintext_bank_credential_phishing.py", "delegate"),
    "TC-6.1b-D2-02": ("ATS-6.1b-D2-02-S03-02", "test_cases/test_input_defense_order_false_positive.py", "delegate"),
    "TC-6.1b-D3-01": ("ATS-6.1b-D3-01-S01-01", "test_cases/test_docx_footer_private_note_injection.py", "pending"),
    "TC-6.1b-D4-02": ("ATS-6.1b-D4-02-S01-01", "test_cases/test_url_encoding_deep_json_parsing_boundary.py", "pending"),
    "TC-6.1b-D5-01": ("ATS-6.1b-D5-01-S01-01", "test_cases/test_complete_initial_settings_extraction.py", "delegate"),
    "TC-6.1b-D5-02": ("ATS-6.1b-D5-02-S01-01", "test_cases/test_forged_system_message_boundary.py", "delegate"),
    "TC-6.1b-D5-03": ("ATS-6.1b-D5-03-S01-01", "test_cases/test_debug_roleplay_without_authority.py", "delegate"),
    "TC-6.1b-D5-04": ("ATS-6.1b-D5-04-S01-01", "test_cases/test_html_comment_external_send_indirect_content_injection.py", "pending"),
    "TC-6.1b-D5-05": ("ATS-6.1b-D5-05-S01-01", "test_cases/test_url_encoding_user_dialog_input_normalization.py", "pending"),
    "TC-6.1b-D6-01": ("ATS-6.1b-D6-01-S01-01", "test_cases/test_docx_footer_input_detection_traceability.py", "pending"),
    "TC-6.1d-D1-01": ("ATS-6.1d-D1-01-S01-01", "test_cases/test_model_text_output_detection_design_review.py", "pending"),
    "TC-6.1d-D1-02": ("ATS-6.1d-D1-02-S01-02", "test_cases/test_direct_text_output_restricted_fields.py", "delegate"),
    "TC-6.1d-D2-01": ("ATS-6.1d-D2-01-S04-05", "test_cases/test_phishing_guidance_plaintext_output.py", "pending"),
    "TC-6.1d-D2-02": ("ATS-6.1d-D2-02-S03-01", "test_cases/test_surname_only_output_reidentification.py", "delegate"),
    "TC-6.1d-D3-01": ("ATS-6.1d-D3-01-S05-01", "test_cases/test_customer_direct_text_output_protection_scope.py", "pending"),
    "TC-6.1d-D4-01": ("ATS-6.1d-D4-01-S03-01", "test_cases/test_response_limit_tail_output_detection.py", "delegate"),
    "TC-6.1d-D5-01": ("ATS-6.1d-D5-01-S02-01", "test_cases/test_inappropriate_content_training_direct_text_output_detection.py", "pending"),
    "TC-6.1d-D5-02": ("ATS-6.1d-D5-02-S01-01", "test_cases/test_two_segment_email_output.py", "delegate"),
    "TC-6.1d-D5-03": ("ATS-6.1d-D5-03-S01-01", "test_cases/test_system_plain_start_output_filter_override.py", "pending"),
    "TC-6.1d-D5-04": ("ATS-6.1d-D5-04-S01-01", "test_cases/test_multilingual_english_output.py", "delegate"),
    "TC-6.1d-D6-01": ("ATS-6.1d-D6-01-S01-01", "test_cases/test_block_event_bidirectional_trace.py", "pending"),
    "TC-6.3d-D6-01": ("ATS-6.3d-D6-01-S01-01", "test_cases/test_permission_monitoring_alert_block_record_fields.py", "pending"),
    "TC-6.4a-D6-01": ("ATS-6.4a-D6-01-S01-01", "test_cases/test_three_risk_tier_log_correlation.py", "pending"),
    "TC-6.4f-D5-02": ("ATS-6.4f-D5-02-S01-01", "test_cases/test_authorized_read_to_write_expansion.py", "pending"),
    "TC-7.1a-D5-02": ("ATS-7.1a-D5-02-S01-01", "test_cases/test_resource_isolation_context_50_percent_character_a_end_rule_override.py", "pending"),
    "TC-7.1c-D1-01": ("ATS-7.1c-D1-01-S01-01", "test_cases/test_runtime_consistency_detection_mounting.py", "pending"),
    "TC-7.1c-D2-01": ("ATS-7.1c-D2-01-S01-01", "test_cases/test_intent_drift_delete_scope.py", "pending"),
    "TC-7.1c-D3-01": ("ATS-7.1c-D3-01-S01-01", "test_cases/test_intent_baseline_untrusted_source_drift_primary.py", "pending"),
    "TC-7.1c-D4-01": ("ATS-7.1c-D4-01-S01-01", "test_cases/test_ambiguous_email_intent_detector_timeout.py", "pending"),
    "TC-7.1c-D5-01": ("ATS-7.1c-D5-01-S01-01", "test_cases/test_contact_broadcast_three_turn_original.py", "pending"),
    "TC-7.1c-D6-01": ("ATS-7.1c-D6-01-S01-01", "test_cases/test_consistent_allow_decision_reconstruction.py", "pending"),
}

P1_OUTPUT_CASES = frozenset(
    {
        "TC-5.2a-D6-01",
        "TC-5.2c-D3-01",
        "TC-5.2d-D6-01",
        "TC-5.2e-D6-01",
        "TC-5.5e-D2-01",
        "TC-6.1b-D6-01",
        "TC-6.1d-D2-01",
        "TC-6.1d-D5-01",
        "TC-6.1d-D5-03",
        "TC-6.1d-D6-01",
        "TC-6.4a-D6-01",
        "TC-7.1c-D6-01",
    }
)
P1_STATE_CASES = frozenset(
    {
        "TC-5.1d-D6-01",
        "TC-5.2a-D2-01",
        "TC-5.2a-D5-01",
        "TC-5.5c-D1-01",
        "TC-5.5c-D1-02",
        "TC-5.5c-D2-02",
        "TC-5.5c-D5-01",
        "TC-6.3d-D6-01",
        "TC-6.4f-D5-02",
        "TC-7.1c-D2-01",
        "TC-7.1c-D4-01",
        "TC-7.1c-D5-01",
    }
)
P1_PROXY_CASES = frozenset(
    {
        "TC-5.2a-D1-01",
        "TC-5.2a-D3-01",
        "TC-6.1b-D3-01",
        "TC-6.1b-D4-02",
        "TC-6.1b-D5-04",
        "TC-6.1b-D5-05",
        "TC-6.1d-D1-01",
        "TC-6.1d-D3-01",
        "TC-7.1a-D5-02",
        "TC-7.1c-D1-01",
        "TC-7.1c-D3-01",
    }
)


def _p1_implementation_mode(source_case_id: str, curated_mode: str) -> str:
    if curated_mode == "delegate":
        return "delegate"
    if source_case_id in P1_OUTPUT_CASES:
        return "p1_output"
    if source_case_id in P1_STATE_CASES:
        return "p1_state"
    if source_case_id in P1_PROXY_CASES:
        return "p1_proxy"
    raise ValueError(f"{source_case_id} has no implemented P1 execution mode")

_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOCUMENT_REL_NS = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
)
_PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_CELL_COLUMN = re.compile(r"[A-Z]+")
_CASE_ID = re.compile(r"TEST_CASE_ID\s*=\s*[\"']([^\"']+)")
_CHILD_ID = re.compile(r"^ATS-(?P<source>.+)-S\d+-.+$")
_SUPPORTED_IMPLEMENTATION_MODES = frozenset(
    {
        "pending",
        "delegate",
        "p1_output",
        "p1_state",
        "p1_proxy",
        "p2_identity",
        "p2_proxy",
        "p2_output",
        "deferred",
    }
)

# Manifest keys intentionally follow the domain language used by the test framework.
_COLUMN_TO_FIELD = {
    "A": "source_case_id",
    "B": "name",
    "C": "test_input",
    "P": "preconditions",
    "R": "steps",
    "S": "expected_result",
    "T": "pass_condition",
    "U": "fail_condition",
    "V": "not_applicable_condition",
    "W": "evidence_requirement",
    "AE": "category",
    "AF": "arrangement",
    "AG": "priority",
    "AH": "required_capability",
    "AI": "uncovered_requirements",
    "AJ": "criteria_version",
    "AM": "experiment_reuse_key",
}


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        stream = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    with stream:
        root = ElementTree.parse(stream).getroot()
    return [
        "".join(node.text or "" for node in item.iter(f"{_MAIN_NS}t"))
        for item in root.findall(f"{_MAIN_NS}si")
    ]


def _worksheet_path(archive: ZipFile, sheet_name: str) -> str:
    with archive.open("xl/workbook.xml") as stream:
        workbook = ElementTree.parse(stream).getroot()
    with archive.open("xl/_rels/workbook.xml.rels") as stream:
        relationships = ElementTree.parse(stream).getroot()

    targets = {
        node.attrib["Id"]: node.attrib["Target"]
        for node in relationships.findall(f"{_PACKAGE_REL_NS}Relationship")
    }
    sheets = workbook.find(f"{_MAIN_NS}sheets")
    if sheets is None:
        raise ValueError("workbook does not contain a sheets collection")
    for sheet in sheets:
        if sheet.attrib.get("name") != sheet_name:
            continue
        relationship_id = sheet.attrib[f"{_DOCUMENT_REL_NS}id"]
        target = targets[relationship_id]
        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))
    raise ValueError(f"workbook does not contain sheet {sheet_name!r}")


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    value = cell.find(f"{_MAIN_NS}v")
    if cell.attrib.get("t") == "s" and value is not None:
        return shared_strings[int(value.text or "0")]
    inline = cell.find(f"{_MAIN_NS}is")
    if inline is not None:
        return "".join(node.text or "" for node in inline.iter(f"{_MAIN_NS}t"))
    return value.text if value is not None and value.text is not None else ""


def read_mother_cases(workbook_path: Path) -> list[dict[str, str]]:
    """Read normalized mother-case rows without requiring an Excel dependency."""

    cases: list[dict[str, str]] = []
    with ZipFile(workbook_path) as archive:
        shared_strings = _shared_strings(archive)
        worksheet_path = _worksheet_path(archive, SHEET_NAME)
        with archive.open(worksheet_path) as stream:
            for _, row in ElementTree.iterparse(stream, events=("end",)):
                if row.tag != f"{_MAIN_NS}row":
                    continue
                values: dict[str, str] = {}
                for cell in row.findall(f"{_MAIN_NS}c"):
                    match = _CELL_COLUMN.match(cell.attrib.get("r", ""))
                    if match:
                        values[match.group()] = _cell_value(cell, shared_strings)
                source_case_id = values.get("A", "").strip()
                if source_case_id.startswith("TC-"):
                    cases.append(
                        {
                            field: values.get(column, "").strip()
                            for column, field in _COLUMN_TO_FIELD.items()
                        }
                    )
                row.clear()
    return cases


def find_child_cases(root: Path) -> dict[str, list[dict[str, str]]]:
    """Group checked-in ATS scripts by the mother-case ID encoded in their ID."""

    grouped: dict[str, list[dict[str, str]]] = {}
    for path in sorted((root / "test_cases").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        match = _CASE_ID.search(source)
        if match is None:
            continue
        child_id = match.group(1)
        child_match = _CHILD_ID.fullmatch(child_id)
        if child_match is None or child_id.startswith("ATS-0.0x-"):
            continue
        source_case_id = f"TC-{child_match.group('source')}"
        grouped.setdefault(source_case_id, []).append(
            {
                "case_id": child_id,
                "script": path.relative_to(root).as_posix(),
            }
        )
    for children in grouped.values():
        children.sort(key=lambda child: child["case_id"])
    return grouped


def _literal_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
    return values


def find_mother_implementations(root: Path) -> dict[str, dict[str, str]]:
    """Read checked-in implementation metadata without importing pytest files."""

    implementations: dict[str, dict[str, str]] = {}
    mother_root = root / "test_cases" / "mother_cases"
    for path in sorted(mother_root.glob("test_tc_*.py")):
        values = _literal_assignments(path)
        source_case_id = str(values.get("TEST_CASE_ID") or "").strip()
        implementation_mode = str(values.get("IMPLEMENTATION_MODE") or "").strip()
        if not implementation_mode:
            continue
        if not source_case_id.startswith("TC-"):
            raise ValueError(f"{path} has invalid TEST_CASE_ID")
        if source_case_id in implementations:
            raise ValueError(f"duplicate implemented mother case: {source_case_id}")
        implementations[source_case_id] = {
            "representative_child_id": str(
                values.get("REPRESENTATIVE_CHILD_ID") or ""
            ).strip(),
            "representative_child_script": str(
                values.get("REPRESENTATIVE_CHILD_SCRIPT") or ""
            ).strip(),
            "implementation_mode": implementation_mode,
        }
    return implementations


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Reject incomplete or internally inconsistent manifest payloads."""

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("manifest cases must be a list")
    if len(cases) != EXPECTED_CASE_COUNT:
        raise ValueError(f"expected {EXPECTED_CASE_COUNT} cases, found {len(cases)}")

    ids = [case.get("source_case_id") for case in cases]
    if len(ids) != len(set(ids)):
        duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
        raise ValueError(f"duplicate mother-case IDs: {duplicates}")
    if any(not isinstance(case_id, str) or not case_id.startswith("TC-") for case_id in ids):
        raise ValueError("every mother-case ID must start with TC-")

    priorities = Counter(case.get("priority") for case in cases)
    if dict(sorted(priorities.items())) != EXPECTED_PRIORITY_COUNTS:
        raise ValueError(
            f"unexpected priority counts: {dict(sorted(priorities.items()))}"
        )
    if manifest.get("case_count") != len(cases):
        raise ValueError("manifest case_count does not match cases")
    if manifest.get("priority_counts") != dict(sorted(priorities.items())):
        raise ValueError("manifest priority_counts does not match cases")

    categories = Counter(case.get("category") for case in cases)
    if manifest.get("category_counts") != dict(sorted(categories.items())):
        raise ValueError("manifest category_counts does not match cases")

    required_fields = set(_COLUMN_TO_FIELD.values())
    for case in cases:
        missing = required_fields.difference(case)
        if missing:
            raise ValueError(f"{case.get('source_case_id')} is missing fields: {missing}")
        blank = {field for field in required_fields if not case[field]}
        if blank:
            raise ValueError(
                f"{case.get('source_case_id')} has blank required fields: {blank}"
            )
        source_case_id = case["source_case_id"]
        expected_prefix = source_case_id.removeprefix("TC-")
        candidates = case.get("representative_child_candidates", [])
        if case.get("child_case_count") != len(candidates):
            raise ValueError(f"{source_case_id} child_case_count does not match candidates")
        child_ids = [child.get("case_id") for child in candidates]
        if len(child_ids) != len(set(child_ids)):
            raise ValueError(f"{source_case_id} contains duplicate child candidates")
        for child in candidates:
            child_id = child.get("case_id", "")
            match = _CHILD_ID.fullmatch(child_id)
            if match is None or match.group("source") != expected_prefix:
                raise ValueError(
                    f"{child_id!r} is not a child of {source_case_id!r}"
                )
        representative_id = case.get("representative_child_id")
        representative_script = case.get("representative_child_script")
        if bool(representative_id) != bool(representative_script):
            raise ValueError(
                f"{source_case_id} representative child ID and script must be paired"
            )
        if representative_id:
            selected = {
                (child.get("case_id"), child.get("script")) for child in candidates
            }
            if (representative_id, representative_script) not in selected:
                raise ValueError(
                    f"{source_case_id} representative child is not a listed candidate"
                )

        implementation_mode = case.get("implementation_mode")
        if implementation_mode not in _SUPPORTED_IMPLEMENTATION_MODES:
            raise ValueError(
                f"{source_case_id} has unsupported implementation_mode: "
                f"{implementation_mode!r}"
            )
        if implementation_mode == "delegate" and not representative_id:
            raise ValueError(
                f"{source_case_id} delegate mode requires a representative child"
            )

    p1_cases = [case for case in cases if case.get("priority") == "P1"]
    if any(not case.get("representative_child_id") for case in p1_cases):
        raise ValueError("every P1 case must identify a representative child")
    mode_counts = dict(
        sorted(Counter(case.get("implementation_mode") for case in p1_cases).items())
    )
    if mode_counts != EXPECTED_P1_MODE_COUNTS:
        raise ValueError(
            f"unexpected P1 implementation modes: {mode_counts}"
        )


def build_manifest(root: Path, workbook_path: Path) -> dict[str, Any]:
    """Build a deterministic manifest from the workbook and repository scripts."""

    child_cases = find_child_cases(root)
    mother_implementations = find_mother_implementations(root)
    cases: list[dict[str, Any]] = []
    for source_case in read_mother_cases(workbook_path):
        source_case_id = source_case["source_case_id"]
        candidates = child_cases.get(source_case_id, [])
        representative = P1_REPRESENTATIVE_PATHS.get(source_case_id)
        implementation = mother_implementations.get(source_case_id)
        representative_child_id = (
            implementation["representative_child_id"]
            if implementation
            else representative[0]
            if representative
            else None
        )
        representative_child_script = (
            implementation["representative_child_script"]
            if implementation
            else representative[1]
            if representative
            else None
        )
        implementation_mode = (
            implementation["implementation_mode"]
            if implementation
            else _p1_implementation_mode(source_case_id, representative[2])
            if representative
            else "pending"
        )
        cases.append(
            {
                **source_case,
                "representative_child_id": representative_child_id,
                "representative_child_script": representative_child_script,
                "implementation_mode": implementation_mode,
                "representative_child_candidates": candidates,
                "child_case_count": len(candidates),
            }
        )
    cases.sort(key=lambda case: (case["priority"], case["source_case_id"]))

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "source": {
            "workbook": workbook_path.name,
            "sheet": SHEET_NAME,
            "sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        },
        "curation_sources": ["docs/p1_mother_case_inventory.md"],
        "case_count": len(cases),
        "priority_counts": dict(
            sorted(Counter(case["priority"] for case in cases).items())
        ),
        "category_counts": dict(
            sorted(Counter(case["category"] for case in cases).items())
        ),
        "cases": cases,
    }
    validate_manifest(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "configs"
        / "mother_cases_v3.json",
    )
    args = parser.parse_args()

    manifest = build_manifest(args.root.resolve(), args.workbook.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": manifest["case_count"],
                "priority_counts": manifest["priority_counts"],
                "category_counts": manifest["category_counts"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
