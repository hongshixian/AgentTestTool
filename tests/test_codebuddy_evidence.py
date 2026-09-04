"""Verify the CodeBuddy trusted-evidence command adapter."""

from __future__ import annotations

import sys

import pytest

from agent_models import EvidencePhase, EvidenceRequest, RequestContext
from agent_models.codebuddy.evidence import CodeBuddyCommandEvidenceProvider


class TestCodeBuddyCommandEvidenceProvider:
    def test_reads_json_evidence_from_command(self, tmp_path) -> None:
        command = (
            sys.executable,
            "-c",
            "import json; print(json.dumps({'evidence': [{'evidence_id': "
            "'authoritative_identity_observation', 'type': 'environment_observation', "
            "'data': {'user_id': 'user-a', 'instance_id': 'instance-a'}}]}))",
        )
        provider = CodeBuddyCommandEvidenceProvider(workspace=tmp_path, command=command)

        records = provider.capture(_request())

        assert len(records) == 1
        assert records[0].evidence_id == "authoritative_identity_observation"
        assert records[0].phase is EvidencePhase.BEFORE

    def test_redacts_token_from_command_failure(self, tmp_path) -> None:
        command = (
            sys.executable,
            "-c",
            "import sys; print(sys.stdin.read(), file=sys.stderr); raise SystemExit(2)",
        )
        provider = CodeBuddyCommandEvidenceProvider(workspace=tmp_path, command=command)

        with pytest.raises(RuntimeError) as captured:
            provider.capture(_request())

        assert "secret-token" not in str(captured.value)
        assert "***" in str(captured.value)


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        sample_id="ATS-5.1b-D5-02-S04",
        prompt_id="LANGUAGE-01",
        repeat_index=1,
        phase=EvidencePhase.BEFORE,
        context=RequestContext(
            authorization="Bearer secret-token",
            user_id="user-a",
            instance_id="instance-a",
            run_id="test-run",
        ),
    )
