"""Offline checks for the pinned OpenCode cancellation source probe."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agent_models.opencode.whitebox import WhiteBoxBindingError
from agent_models.opencode.whitebox_cancel import (
    CANCEL_HASHES,
    _MARKERS,
    OpenCodeWhiteBoxCancelHarness,
)


SOURCE = Path(os.environ["OPENCODE_WHITEBOX_SOURCE"]) if os.environ.get("OPENCODE_WHITEBOX_SOURCE") else None


@pytest.fixture
def source_root(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    root = tmp_path / "source"
    by_file: dict[str, list[str]] = {}
    for path, marker in _MARKERS.values():
        by_file.setdefault(path, []).append(marker)
    for path, markers in by_file.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(markers), encoding="utf-8")
    package = root / "packages/opencode/package.json"
    package.write_text(json.dumps({"version": "1.18.32"}), encoding="utf-8")
    script = tmp_path / "version.py"
    script.write_text("print('1.18.32')\n", encoding="utf-8")
    hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in by_file}
    hashes["packages/opencode/package.json"] = hashlib.sha256(package.read_bytes()).hexdigest()
    return root, hashes, script


def _harness(source_root: tuple[Path, dict[str, str], Path]) -> OpenCodeWhiteBoxCancelHarness:
    root, hashes, script = source_root
    return OpenCodeWhiteBoxCancelHarness(
        root, cli_command=(sys.executable, str(script)), binary_path=Path(sys.executable),
        expected_hashes=hashes,
    )


def test_maps_w085_and_w086_production_boundaries_without_claiming_verdict(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    mapping = _harness(source_root).map_cancel_boundaries()

    assert mapping.binding.source_hashes == source_root[1]
    assert set(mapping.locations) == set(_MARKERS)
    assert mapping.locations["background_traversal"].startswith(
        "packages/opencode/src/session/run-state.ts:"
    )
    assert "all three stop points" in mapping.missing_for_w085[1]
    assert "real BackgroundJob.start" in mapping.missing_for_w086[1]


def test_rejects_mutated_source_even_if_cancel_marker_is_still_present(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source_root
    target = root / "packages/opencode/src/session/run-state.ts"
    target.write_text(target.read_text() + "\n// mutated", encoding="utf-8")
    with pytest.raises(WhiteBoxBindingError, match="Source digest mismatch"):
        _harness(source_root).probe_job_traversal()

    target.write_text(
        target.read_text().replace('const cancel = Effect.fn("SessionRunState.cancel")', "const cancel = () =>"),
        encoding="utf-8",
    )
    hashes["packages/opencode/src/session/run-state.ts"] = hashlib.sha256(target.read_bytes()).hexdigest()
    with pytest.raises(WhiteBoxBindingError, match="Production cancel boundary ambiguous"):
        _harness(source_root).map_cancel_boundaries()


def test_rejects_mismatched_installed_binary_version(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    source_root[2].write_text("print('0.0.1')\n", encoding="utf-8")
    with pytest.raises(WhiteBoxBindingError, match="does not match pinned source"):
        _harness(source_root).map_cancel_boundaries()


def test_traversal_probe_executes_only_verified_private_snapshot(
    source_root: tuple[Path, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(source_root)
    boundary = harness.map_cancel_boundaries()
    monkeypatch.setattr(harness, "map_cancel_boundaries", lambda: boundary)
    source = source_root[0] / "packages/opencode/src/session/run-state.ts"
    original = source.read_bytes()
    observations = [
        {"graph": graph, "expected": expected, "cancel_spy": expected,
         "uncancelled": [], "unrelated_running": True, "traversal_terminated": True}
        for graph, expected in (("A-B-C", ["B", "C"]), ("A-B-A", ["A", "B"]))
    ]

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        snapshot = Path(command[-1])
        assert snapshot.is_relative_to(Path(str(kwargs["cwd"])))
        source.write_text("changed after snapshot\n", encoding="utf-8")
        assert snapshot.read_bytes() == original
        return subprocess.CompletedProcess(command, 0, json.dumps(observations))

    monkeypatch.setattr("agent_models.opencode.whitebox_cancel.subprocess.run", run)
    assert len(harness.probe_job_traversal().observations) == 2


def test_traversal_probe_rejects_checkout_change_after_binding(
    source_root: tuple[Path, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(source_root)
    boundary = harness.map_cancel_boundaries()
    source = source_root[0] / "packages/opencode/src/session/run-state.ts"
    source.write_text(source.read_text(encoding="utf-8") + "\n// changed after binding\n", encoding="utf-8")
    monkeypatch.setattr(harness, "map_cancel_boundaries", lambda: boundary)

    with pytest.raises(WhiteBoxBindingError, match="source digest changed after binding"):
        harness.probe_job_traversal()


@pytest.mark.skipif(
    SOURCE is None or not SOURCE.is_dir() or shutil.which("node") is None or shutil.which("opencode") is None,
    reason="Pinned OpenCode source, matching CLI and Node.js are required",
)
def test_pinned_production_traversal_probes_chain_and_cycle() -> None:
    assert SOURCE is not None
    probe = OpenCodeWhiteBoxCancelHarness(SOURCE).probe_job_traversal()

    assert probe.binding.checkout_commit == "545f51d26cc39a907d2867492d498d9607ea5fa4"
    assert probe.binding.source_hashes == CANCEL_HASHES
    assert {item["graph"] for item in probe.observations} == {"A-B-C", "A-B-A"}
    assert all(
        sorted(item["cancel_spy"]) == item["expected"]
        and item["uncancelled"] == []
        and item["unrelated_running"]
        and item["traversal_terminated"]
        for item in probe.observations
    )
    assert "actual SessionPrompt.cancel" in probe.missing_for_w086[-1]


@pytest.mark.skipif(
    SOURCE is None or not SOURCE.is_dir() or shutil.which("node") is None,
    reason="Pinned OpenCode source and Node.js are required",
)
def test_probe_rejects_chain_regression_even_when_fixture_digest_is_updated(tmp_path: Path) -> None:
    assert SOURCE is not None
    root = tmp_path / "source"
    for name in CANCEL_HASHES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
    script = tmp_path / "version.py"
    script.write_text("print('1.18.32')\n", encoding="utf-8")
    run_state = root / "packages/opencode/src/session/run-state.ts"
    original = run_state.read_text(encoding="utf-8")
    assert original.count("pending.add(job.id)") == 1
    assert original.count("pending.add(job.metadata.sessionId)") == 1
    run_state.write_text(
        original.replace("pending.add(job.id)", "pending.add('not-a-job')")
        .replace("pending.add(job.metadata.sessionId)", "pending.add('not-a-session')"),
        encoding="utf-8",
    )
    hashes = dict(CANCEL_HASHES)
    hashes["packages/opencode/src/session/run-state.ts"] = hashlib.sha256(run_state.read_bytes()).hexdigest()
    probe = OpenCodeWhiteBoxCancelHarness(
        root, cli_command=(sys.executable, str(script)), binary_path=Path(sys.executable),
        expected_hashes=hashes,
    )

    with pytest.raises(WhiteBoxBindingError, match="did not cancel both child graphs"):
        probe.probe_job_traversal()
