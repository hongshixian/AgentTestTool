"""Verify resumable one-by-one mother-case execution bookkeeping."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_mother_cases import (
    MotherScript,
    _literal_constants,
    _validate_result,
    _verified_for_current_script,
    discover_scripts,
)


def test_literal_constants_does_not_import_test_module(tmp_path: Path) -> None:
    script = tmp_path / "test_case.py"
    script.write_text(
        "TEST_CASE_ID = 'TC-EXAMPLE'\n"
        "TEST_CASE_LEVEL = 'mother'\n"
        "raise RuntimeError('must not import')\n",
        encoding="utf-8",
    )

    constants = _literal_constants(script)

    assert constants == {
        "TEST_CASE_ID": "TC-EXAMPLE",
        "TEST_CASE_LEVEL": "mother",
    }


def test_discovery_returns_unique_manifest_aligned_scripts() -> None:
    scripts = discover_scripts()

    assert scripts
    assert len({script.case_id for script in scripts}) == len(scripts)
    assert all(script.path.is_file() for script in scripts)
    assert all(len(script.sha256) == 64 for script in scripts)


def test_validate_result_requires_one_matching_four_state_case(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "test_case_id": "TC-EXAMPLE",
                        "status": "不适用",
                        "reason": "真实能力不支持",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert _validate_result(result, "TC-EXAMPLE") == (
        True,
        "不适用",
        "真实能力不支持",
    )
    valid, _status, reason = _validate_result(result, "TC-OTHER")
    assert valid is False
    assert "ID 不匹配" in reason


def test_resume_requires_latest_verified_attempt_for_same_script(tmp_path: Path) -> None:
    path = tmp_path / "test_tc_example.py"
    path.write_text("TEST_CASE_ID='TC-EXAMPLE'\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    script = MotherScript("TC-EXAMPLE", path, "P1", "J", digest)
    index = {
        "cases": {
            "TC-EXAMPLE": {
                "script_sha256": digest,
                "attempts": [{"verified": True, "status": "通过"}],
            }
        }
    }

    assert _verified_for_current_script(index, script) is True
    changed = MotherScript("TC-EXAMPLE", path, "P1", "J", "0" * 64)
    assert _verified_for_current_script(index, changed) is False
