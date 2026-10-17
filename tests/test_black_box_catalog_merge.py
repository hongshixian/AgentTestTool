"""Regression tests for batch-agnostic black-box case IDs and merged catalogs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_cases.black_box.models import BlackBoxCaseSpec
from test_cases.black_box.specs import catalog_paths, load_black_box_spec, load_black_box_specs


def _catalog(path: Path, *case_ids: str) -> Path:
    path.write_text(
        json.dumps({"cases": [
            {
                "case_id": case_id,
                "title": f"case {case_id}",
                "steps": [{"phase_id": "exercise", "prompt": "say PUBLIC_OK"}],
            }
            for case_id in case_ids
        ]}),
        encoding="utf-8",
    )
    return path


def test_case_ids_are_opaque_strings() -> None:
    for case_id in ("B001", "T292", "OFFICE-01", "case.a_1"):
        spec = BlackBoxCaseSpec(case_id, "title", 1, 10)
        assert spec.case_id == case_id


def test_empty_case_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="case ID must be nonempty"):
        BlackBoxCaseSpec("  ", "title", 1, 10)


def test_explicit_path_loads_a_single_catalog(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path / "black_box_t_batch.json", "T001", "T002")

    specs = load_black_box_specs(catalog)

    assert list(specs) == ["T001", "T002"]
    assert load_black_box_spec("T002", catalog).title == "case T002"


def test_duplicate_ids_across_catalogs_are_rejected(tmp_path: Path, monkeypatch) -> None:
    import test_cases.black_box.specs as specs_module

    _catalog(tmp_path / "black_box_a.json", "T001")
    _catalog(tmp_path / "black_box_b.json", "T001")
    monkeypatch.setattr(specs_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(ValueError, match="defined in both"):
        load_black_box_specs()


def test_discovery_merges_every_black_box_manifest(tmp_path: Path, monkeypatch) -> None:
    import test_cases.black_box.specs as specs_module

    _catalog(tmp_path / "black_box_cases.json", "B001")
    _catalog(tmp_path / "black_box_office_cases.json", "T001")
    (tmp_path / "grey_box_cases.json").write_text('{"cases": []}', encoding="utf-8")
    monkeypatch.setattr(specs_module, "CONFIG_DIR", tmp_path)

    assert [path.name for path in catalog_paths()] == [
        "black_box_cases.json",
        "black_box_office_cases.json",
    ]
    assert list(load_black_box_specs()) == ["B001", "T001"]


def test_missing_discovery_target_is_an_error(tmp_path: Path, monkeypatch) -> None:
    import test_cases.black_box.specs as specs_module

    monkeypatch.setattr(specs_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(ValueError, match="no black-box catalog"):
        load_black_box_specs()
