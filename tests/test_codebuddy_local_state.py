"""Verify the CodeBuddy local-state command adapter."""

from __future__ import annotations

import sys

from agent_models import LocalStateAction, LocalStateKind, LocalStateRequest, RequestContext
from agent_models.codebuddy.local_state import CodeBuddyCommandLocalStateController


class TestCodeBuddyCommandLocalStateController:
    def test_maps_prepare_and_restore_to_evidence_phases(self, tmp_path) -> None:
        script = (
            "import json,sys; request=json.load(sys.stdin); "
            "print(json.dumps({'evidence':[{'evidence_id':request['action'],"
            "'type':'runtime_evidence','data':{'action':request['action']}}]}))"
        )
        controller = CodeBuddyCommandLocalStateController(
            workspace=tmp_path,
            command=(sys.executable, "-c", script),
        )
        request = LocalStateRequest(
            sample_id="ATS-5.1b-D5-02-S03",
            prompt_id="LOCAL-STATE-01",
            repeat_index=1,
            run_id="run-1",
            device="test-device",
            kind=LocalStateKind.JSON,
            target_instance_id="instance-b",
            context=RequestContext("user-a", "instance-a", "run-1"),
        )

        prepared = controller.execute(LocalStateAction.PREPARE, request)
        restored = controller.execute(LocalStateAction.RESTORE, request)

        assert prepared[0].phase.value == "before"
        assert prepared[0].data == {"action": "prepare"}
        assert restored[0].phase.value == "after"
        assert restored[0].data == {"action": "restore"}
