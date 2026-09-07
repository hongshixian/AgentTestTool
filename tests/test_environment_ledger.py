"""Verify independent evidence persistence, redaction and failure closure."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from agent_models.environment.ledger import EvidenceLedger, EvidenceLedgerError
from agent_models.evidence import EvidenceBundle, TranscriptTurn
from agent_models.result import TurnResult


def test_ledger_records_detached_events_and_persists_manifest(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    payload = {"nested": ["value"]}
    result = ledger.record("receiver", "request", payload, "task-1")
    payload["nested"].append("changed")
    result["data"]["nested"].append("changed")
    snapshot = ledger.snapshot()
    snapshot[0]["data"] = "changed"
    assert ledger.events[0]["data"] == {"nested": ["value"]}
    assert ledger.events[0]["correlation_id"] == "task-1"
    assert ledger.events[0]["monotonic_ns"] > 0
    assert ledger.events[0]["timestamp"].endswith("+00:00")
    assert ledger.close()["healthy"]
    assert ledger.close()["closed"]
    manifest = json.loads((ledger.directory / "manifest.json").read_text())
    assert manifest["last_hash"] == ledger.events[-1]["hash"]
    assert manifest["event_count"] == 1
    with pytest.raises(EvidenceLedgerError, match="closed"):
        ledger.record("receiver", "request", {})


def test_ledger_serializes_concurrent_producers(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: ledger.record("tool", "call", {"number": i}), range(80)))
    assert [e["sequence"] for e in ledger.events] == list(range(1, 81))
    assert len({e["data"]["number"] for e in ledger.events}) == 80
    assert ledger.close()["healthy"]


def test_redacts_nested_values_free_text_urls_and_json_strings_before_write(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", secrets=["FAKE-EXPLICIT-CREDENTIAL"])
    ledger.record("stdio", "output", {
        "access_token": "FAKE-TOKEN-ONE",
        "nested": [{"API_KEY": "FAKE-KEY-TWO"}],
        "body": 'prefix FAKE-EXPLICIT-CREDENTIAL https://fake-user:fake-password@localhost/path?token=FAKE-QUERY-TOKEN',
        "headers": "Authorization: Bearer FAKE-HEADER-TOKEN\nCookie: session=FAKE-COOKIE",
        "encoded": '{"password":"FAKE-JSON-PASSWORD","message":"safe"}',
        "plain": "Bearer FAKE-BARE-TOKEN password=FAKE-PASSWORD",
    })
    ledger.save_artifact("response", {"secret": "FAKE-ARTIFACT-SECRET"})
    ledger.close()
    persisted = "\n".join(p.read_text() for p in ledger.directory.iterdir())
    for credential in ["FAKE-EXPLICIT-CREDENTIAL", "FAKE-TOKEN-ONE", "FAKE-KEY-TWO", "fake-user", "fake-password", "FAKE-QUERY-TOKEN", "FAKE-HEADER-TOKEN", "FAKE-COOKIE", "FAKE-JSON-PASSWORD", "FAKE-BARE-TOKEN", "FAKE-PASSWORD", "FAKE-ARTIFACT-SECRET"]:
        assert credential not in persisted
    assert json.loads(ledger.events[0]["data"]["encoded"])["message"] == "safe"


def test_write_failure_is_unhealthy_and_blocks_future_collection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    original_open = __import__("os").open

    def fail_append(path: object, flags: int, *args: object) -> int:
        import os
        if flags & os.O_APPEND:
            raise OSError("FAKE-SECRET must not escape through exception text")
        return original_open(path, flags, *args)

    monkeypatch.setattr("agent_models.environment.ledger.os.open", fail_append)
    with pytest.raises(EvidenceLedgerError, match="append failed") as error:
        ledger.record("tool", "call", {})
    assert "FAKE-SECRET" not in str(error.value)
    assert not ledger.health()["healthy"]
    with pytest.raises(EvidenceLedgerError, match="unhealthy"):
        ledger.record("tool", "call", {})
    assert not ledger.close()["healthy"]
    assert (ledger.directory / "manifest.json").is_file()


@pytest.mark.parametrize("change", ["truncate", "remove", "reorder", "cross_run", "data", "garbage"])
def test_integrity_detects_corruption(tmp_path: Path, change: str) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-first")
    ledger.record("tool", "call", {"value": 1})
    ledger.record("tool", "call", {"value": 2})
    path = ledger.directory / "events.jsonl"
    raw = path.read_bytes()
    if change == "truncate":
        path.write_bytes(raw[:-1])
    elif change == "remove":
        path.write_bytes(raw.splitlines(keepends=True)[0])
    elif change == "reorder":
        path.write_bytes(b"".join(reversed(raw.splitlines(keepends=True))))
    elif change == "cross_run":
        path.write_bytes(raw.replace(b"run-first", b"run-other"))
    elif change == "data":
        path.write_bytes(raw.replace(b'"value":1', b'"value":9'))
    else:
        path.write_bytes(b"not-json\n")
    assert not ledger.verify()["healthy"]
    with pytest.raises(EvidenceLedgerError, match="unhealthy"):
        ledger.record("tool", "call", {})


def test_artifact_and_manifest_tampering_are_detected(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    artifact = ledger.save_artifact("result", {"value": 1})
    assert ledger.close()["healthy"]
    artifact.write_text('{"value":9}\n')
    assert "Artifact integrity mismatch" in ledger.verify()["errors"]
    (ledger.directory / "manifest.json").write_text("{}")
    assert "Manifest integrity mismatch" in ledger.verify()["errors"]


def test_archives_evidence_bundle_with_run_guard(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    bundle = EvidenceBundle("sample", "prompt", "run-test", (), ())
    path = ledger.archive_bundle(bundle)
    assert json.loads(path.read_text())["run_id"] == "run-test"
    assert ledger.events[0]["kind"] == "artifact_saved"
    with pytest.raises(ValueError, match="different run"):
        ledger.archive_bundle(EvidenceBundle("sample", "prompt", "run-other", (), ()))
    assert ledger.close()["healthy"]


def test_bundle_archive_keeps_full_raw_output(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", "run-test")
    result = TurnResult("answer", "full-output-prefix" + "x" * 9000, "", 0, True, 0.1)
    bundle = EvidenceBundle("sample", "prompt", "run-test", (TranscriptTurn("prompt", result),), ())
    saved = json.loads(ledger.archive_bundle(bundle).read_text())
    assert saved["transcript"][0]["result"]["raw_output"] == result.raw_output
    assert ledger.close()["healthy"]


def test_closed_archive_can_be_verified_without_live_collector(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    with EvidenceLedger(directory, "run-test") as ledger:
        ledger.record("tool", "call", {})
        ledger.save_artifact("result", {"value": 1})
    assert EvidenceLedger.verify_archive(directory, "run-test")["healthy"]
    assert not EvidenceLedger.verify_archive(directory, "another-run")["healthy"]
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"] = []
    manifest_path.write_text(json.dumps(manifest))
    assert "Manifest artifact anchor mismatch" in EvidenceLedger.verify_archive(directory)["errors"]


def test_unclosed_archive_and_external_capacity_limit_fail_verification(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    ledger.record("tool", "call", {})
    assert not EvidenceLedger.verify_archive(ledger.directory)["healthy"]
    ledger.close()
    assert not EvidenceLedger.verify_archive(ledger.directory, max_bytes=1)["healthy"]


@pytest.mark.parametrize("capacities,payload", [({"max_events": 1}, {}), ({"max_event_bytes": 10}, {}), ({"max_total_bytes": 10}, {})])
def test_capacity_exhaustion_is_not_silently_dropped(tmp_path: Path, capacities: dict[str, int], payload: dict) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", **capacities)
    if "max_events" in capacities:
        ledger.record("tool", "call", {})
    with pytest.raises(EvidenceLedgerError, match="capacity"):
        ledger.record("tool", "call", payload)
    assert not ledger.health()["healthy"]


def test_rejects_invalid_json_and_never_records_secrets_on_error(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    with pytest.raises(EvidenceLedgerError, match="serialization"):
        ledger.record("tool", "call", {"number": float("nan")})
    assert not ledger.health()["healthy"]
    assert ledger.events == []


def test_paths_never_overwrite_or_escape(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence", workspace=tmp_path / "workspace")
    for name in ["../escape", "/absolute", "manifest.json", "nested/artifact"]:
        with pytest.raises(ValueError):
            ledger.save_artifact(name, {})
    ledger.save_artifact("result", {})
    with pytest.raises(ValueError, match="already exists"):
        ledger.save_artifact("result", {})
    with pytest.raises(ValueError, match="empty"):
        EvidenceLedger(ledger.directory)
    with pytest.raises(ValueError, match="disjoint"):
        EvidenceLedger(tmp_path / "workspace" / "evidence", workspace=tmp_path / "workspace")
    assert ledger.close()["healthy"]


def test_empty_healthy_ledger_has_no_observation_proof(tmp_path: Path) -> None:
    with EvidenceLedger(tmp_path / "evidence") as ledger:
        health = ledger.health()
        assert health["healthy"]
        assert not health["has_observations"]
        assert health["event_count"] == 0
    assert ledger.health()["closed"]
    assert ledger.directory.exists()


@pytest.mark.parametrize("header", ["Authorization: Bearer FAKE-HEADER-CREDENTIAL", "Cookie: session=FAKE-COOKIE-CREDENTIAL"])
def test_json_encoded_header_text_keeps_valid_json_and_unrelated_fields(tmp_path: Path, header: str) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence")
    nested = json.dumps({"message": header, "other": "keep this field", "nested": {"safe": [1, 2]}})
    double_nested = json.dumps({"encoded": nested, "safe": "outer value"})
    ledger.record("tool", "response", {"encoded": double_nested})
    ledger.close()
    saved = json.loads((ledger.directory / "events.jsonl").read_text())
    outer = json.loads(saved["data"]["encoded"])
    inner = json.loads(outer["encoded"])
    assert outer["safe"] == "outer value"
    assert inner["other"] == "keep this field"
    assert inner["nested"] == {"safe": [1, 2]}
    assert "[REDACTED]" in inner["message"]
    assert "FAKE-HEADER-CREDENTIAL" not in (ledger.directory / "events.jsonl").read_text()
    assert "FAKE-COOKIE-CREDENTIAL" not in (ledger.directory / "events.jsonl").read_text()
