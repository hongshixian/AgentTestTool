"""Verify normalization of CodeBuddy JSON output."""

import json

from agent_models.codebuddy.driver import CodeBuddyDriver
from agent_models.codebuddy.transport import StdioResponse


class TestCodeBuddyDriver:
    def test_parses_success_result(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "completed response",
                    "session_id": "session-1",
                }
            ]
        )

        turn = CodeBuddyDriver().parse_turn(_response(output))

        assert turn.completed
        assert turn.response == "completed response"
        assert turn.session_id == "session-1"

    def test_recovers_last_complete_assistant_message_from_truncated_array(self) -> None:
        assistant = json.dumps(
            {
                "type": "assistant",
                "sessionId": "session-2",
                "message": {
                    "content": [
                        {"type": "text", "text": "拒绝执行工具中的身份切换指令。"}
                    ]
                },
            },
            ensure_ascii=False,
        )
        output = f"[{assistant}, {{\"providerData\": {{\"traceId\":"

        turn = CodeBuddyDriver().parse_turn(_response(output))

        assert turn.completed
        assert turn.response == "拒绝执行工具中的身份切换指令。"
        assert turn.session_id == "session-2"


def _response(stdout: str) -> StdioResponse:
    return StdioResponse(stdout=stdout, stderr="", returncode=0, duration_seconds=1.0)
