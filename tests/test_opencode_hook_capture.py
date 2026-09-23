"""Offline OpenCode plugin hook contract and bounded evidence regression tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_models.evidence import EvidencePhase, EvidenceRequest, EvidenceStatus, RequestContext
from agent_models.opencode.hooks import OpenCodeHookCapture


@pytest.fixture
def capture(tmp_path: Path) -> OpenCodeHookCapture:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    return OpenCodeHookCapture(
        evidence_directory=evidence, workspace=workspace, run_id="run-1"
    )


def _request(session: str = "ses-one") -> EvidenceRequest:
    return EvidenceRequest(
        "H071", "01", 1, EvidencePhase.AFTER,
        context=RequestContext("test", None, "run-1"), session_id=session,
    )


def _write_event(capture: OpenCodeHookCapture, **overrides: object) -> None:
    event = {
        "schema_version": 1, "run_id": "run-1", "session_id": "ses-one",
        "turn_id": "turn-1", "kind": "chat.params", "observed_at": "2026-09-23T00:00:00Z",
        **overrides,
    }
    with capture.path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")


def test_prepare_private_file_and_blackbox_has_no_capture(capture: OpenCodeHookCapture, tmp_path: Path) -> None:
    assert capture.path.stat().st_mode & 0o077 == 0 or os.name == "nt"
    assert capture.checkpoint() == 0
    profile = tmp_path / "profile"
    profile.mkdir()
    plugin = capture.install(isolated_config_dir=profile)
    assert plugin.name == "ats_grey_box.js"
    assert plugin.parent.name == "plugin"
    assert plugin.is_file()
    with pytest.raises(ValueError, match="exists"):
        capture.install(isolated_config_dir=profile)
    blackbox = capture.process_environment(
        {"ATS_OC_HOOK_FILE": "attacker", "KEEP_ME": "yes"},
        case_level="black_box",
    )
    assert blackbox == {"KEEP_ME": "yes"}
    assert capture.process_environment(blackbox, case_level="grey_box", turn_id="turn-1") == {
        "KEEP_ME": "yes", "ATS_OC_HOOK_CASE_LEVEL": "grey_box",
        "ATS_OC_HOOK_FILE": str(capture.path), "ATS_OC_HOOK_RUN_ID": "run-1",
        "ATS_OC_HOOK_TURN_ID": "turn-1",
    }


def test_window_isolated_hook_evidence_is_partial_and_redacted(capture: OpenCodeHookCapture) -> None:
    _write_event(capture, turn_id="old-turn")
    offset = capture.checkpoint()
    _write_event(capture, kind="chat.params", user_message_id="msg-new", model_id="provider/model")
    _write_event(capture, kind="tool.execute.before", tool_name="read", tool_call_id="tool-1")
    _write_event(capture, kind="tool.execute.after", tool_name="read", tool_call_id="tool-1")
    record = capture.capture(
        _request(), offset=offset, turn_id="turn-1", redactor=lambda value: value,
    )
    assert record.status is EvidenceStatus.AVAILABLE
    assert record.correlation.run_id == "run-1"
    assert record.correlation.session_ids == ("ses-one",)
    assert record.correlation.turn_ids == ("turn-1",)
    assert record.correlation.tool_use_ids == ("tool-1",)
    assert [event["kind"] for event in record.data["events"]] == [
        "chat.params", "tool.execute.before", "tool.execute.after",
    ]
    assert record.data["complete_observation"] is False
    assert "complete provider request" in record.limitations[0]


@pytest.mark.parametrize("field,value", [
    ("run_id", "another-run"), ("session_id", "ses-other"),
    ("turn_id", "another-turn"), ("unvalidated", "secret-payload"),
    ("kind", "collector_overflow"),
])
def test_invalid_provenance_or_overflow_fails_closed(
    capture: OpenCodeHookCapture, field: str, value: str,
) -> None:
    _write_event(capture, **{field: value})
    record = capture.capture(_request(), turn_id="turn-1")
    assert record.status is EvidenceStatus.UNVERIFIED
    assert record.data == {"events": []}
    assert "secret-payload" not in json.dumps(record.diagnostic_payload())


def test_unattributed_tool_event_is_not_assignable_to_turn(capture: OpenCodeHookCapture) -> None:
    _write_event(capture, kind="tool.execute.after", turn_id=None)
    assert capture.capture(_request()).status is EvidenceStatus.UNVERIFIED


def test_missing_or_truncated_file_does_not_support_assertions(capture: OpenCodeHookCapture) -> None:
    assert capture.capture(_request()).status is EvidenceStatus.MISSING
    capture.path.write_text('{"schema_version": 1', encoding="utf-8")
    assert capture.capture(_request()).status is EvidenceStatus.UNVERIFIED


def test_evidence_must_be_outside_workspace_and_private(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    inside = workspace / "evidence"
    inside.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="outside"):
        OpenCodeHookCapture(evidence_directory=inside, workspace=workspace, run_id="run-1")
    if os.name != "nt":
        world_readable = tmp_path / "readable"
        world_readable.mkdir(mode=0o755)
        world_readable.chmod(0o755)
        with pytest.raises(ValueError, match="private"):
            OpenCodeHookCapture(
                evidence_directory=world_readable, workspace=workspace, run_id="run-1",
            )


@pytest.mark.skipif(shutil.which("node") is None, reason="node unavailable")
def test_actual_js_plugin_emits_only_sanitized_metadata(capture: OpenCodeHookCapture, tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    plugin = capture.install(isolated_config_dir=profile)
    environment = capture.process_environment(os.environ, case_level="grey_box", turn_id="turn-1")
    script = """
import {pathToFileURL} from 'node:url';
const {AtsGreyBoxEvidence} = await import(pathToFileURL(process.argv[1]).href);
const hooks = await AtsGreyBoxEvidence();
const secret = 'very-private-test-secret';
const headers = {authorization:secret};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'build'}, message:{id:'msg-1', content:secret}}, {headers});
if (headers['x-turn-id'] !== 'turn-1' || headers['x-ats-oc-agent'] !== 'build' || headers.authorization !== secret)
  throw new Error('typed turn headers not injected into model request');
const title = {headers:{}};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'title'}, message:{id:'msg-1'}}, title);
if (title.headers['x-turn-id'] !== 'turn-1' || title.headers['x-ats-oc-agent'] !== 'title')
  throw new Error('title agent not classified');
await hooks['chat.params'](
  {sessionID:'ses-one', message:{id:'msg-1', content:secret},
    model:{id:'model-1', apiKey:secret}},
  {temperature:0.3, options:{apiKey:secret, headers:{Authorization:secret}}});
await hooks['tool.execute.before'](
  {sessionID:'ses-one', tool:'read', callID:'call-1', args:{token:secret}},
  {args:{token:secret}});
await hooks['tool.execute.after'](
  {sessionID:'ses-one', tool:'read', callID:'call-1'},
  {output:secret, metadata:{token:secret}});
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(plugin)],
        env=environment, cwd=tmp_path, capture_output=True, text=True,
        timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    raw = capture.path.read_text(encoding="utf-8")
    assert "very-private-test-secret" not in raw
    assert "apiKey" not in raw
    assert "Authorization" not in raw
    record = capture.capture(_request(), turn_id="turn-1")
    assert record.status is EvidenceStatus.AVAILABLE
    assert len(record.data["events"]) == 3
    assert record.data["events"][0]["user_message_id"] == "msg-1"


@pytest.mark.skipif(shutil.which("node") is None, reason="node unavailable")
def test_wire_header_injection_needs_valid_one_shot_turn_and_session(
    capture: OpenCodeHookCapture, tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    plugin = capture.install(isolated_config_dir=profile)
    script = """
import {pathToFileURL} from 'node:url';
const {AtsGreyBoxEvidence} = await import(pathToFileURL(process.argv[1]).href);
const hooks = await AtsGreyBoxEvidence();
const valid = {headers:{'x-other':'public'}};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'build'}}, valid);
if (valid.headers['x-turn-id'] !== 'turn-1' || valid.headers['x-ats-oc-agent'] !== 'build' || valid.headers['x-other'] !== 'public')
  throw new Error('safe nonce not set');
const invalid = {headers:{}};
await hooks['chat.headers']({sessionID:'ses wrong', agent:{name:'build'}}, invalid);
if ('x-turn-id' in invalid.headers) throw new Error('invalid session accepted');
const conflict = {headers:{'X-Turn-Id':'turn-foreign'}};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'build'}}, conflict);
if ('x-turn-id' in conflict.headers) throw new Error('conflicting turn overwritten');
const unknown = {headers:{}};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'bad agent'}}, unknown);
if ('x-turn-id' in unknown.headers || 'x-ats-oc-agent' in unknown.headers)
  throw new Error('unsafe agent name accepted');
const typed = {headers:{}};
await hooks['chat.headers']({sessionID:'ses-one', agent:'build'}, typed);
if (typed.headers['x-ats-oc-agent'] !== 'build') throw new Error('typed string agent unsupported');
"""
    base = capture.process_environment(os.environ, case_level="grey_box", turn_id="turn-1")
    success = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(plugin)],
        env=base, cwd=tmp_path, capture_output=True, text=True,
        timeout=10, check=False,
    )
    assert success.returncode == 0, success.stderr
    for turn in (None, "invalid turn"):
        environment = dict(base)
        if turn is None:
            environment.pop("ATS_OC_HOOK_TURN_ID")
        else:
            environment["ATS_OC_HOOK_TURN_ID"] = turn
        absent = subprocess.run(
            ["node", "--input-type=module", "-e", """
import {pathToFileURL} from 'node:url';
const {AtsGreyBoxEvidence} = await import(pathToFileURL(process.argv[1]).href);
const hooks = await AtsGreyBoxEvidence();
const output = {headers:{}};
await hooks['chat.headers']({sessionID:'ses-one', agent:{name:'build'}}, output);
if ('x-turn-id' in output.headers) throw new Error('missing/invalid nonce accepted');
""", str(plugin)],
            env=environment, cwd=tmp_path, capture_output=True, text=True,
            timeout=10, check=False,
        )
        assert absent.returncode == 0, absent.stderr
    assert capture.path.stat().st_size == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node unavailable")
def test_actual_js_plugin_stays_off_for_blackbox(capture: OpenCodeHookCapture, tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    plugin = capture.install(isolated_config_dir=profile)
    environment = capture.process_environment(os.environ, case_level="black_box")
    script = """
import {pathToFileURL} from 'node:url';
const {AtsGreyBoxEvidence} = await import(pathToFileURL(process.argv[1]).href);
const hooks = await AtsGreyBoxEvidence();
if (Object.keys(hooks).length !== 0) throw new Error('black-box hooks were enabled');
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(plugin)],
        env=environment, cwd=tmp_path, capture_output=True, text=True,
        timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert capture.path.stat().st_size == 0
