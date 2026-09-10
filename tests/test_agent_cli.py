"""Verify CLI manifest validation for bounded business runs."""

import json
from pathlib import Path

import pytest

from agent_test_tool.cli import _manifest_paths


def test_manifest_paths_load_repository_test_case(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {"script": "test_cases/test_plaintext_rule_override_sample_01.py"},
                    {"script": "test_cases/test_plaintext_rule_override_sample_01.py"},
                ]
            }
        ),
        encoding="utf-8",
    )

    paths = _manifest_paths(manifest)

    assert len(paths) == 1
    assert paths[0].name == "test_plaintext_rule_override_sample_01.py"


@pytest.mark.parametrize(
    "script",
    ["README.md", "test_cases/scenarios/not_a_root_case.py", "../test_cases/test_x.py"],
)
def test_manifest_paths_reject_out_of_scope_scripts(
    tmp_path: Path,
    script: str,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"cases": [{"script": script}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        _manifest_paths(manifest)
