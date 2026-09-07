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

    def test_truncated_array_preserves_text_without_claiming_completion(self) -> None:
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

        assert not turn.completed
        assert turn.response == "拒绝执行工具中的身份切换指令。"
        assert turn.session_id == "session-2"

    def test_assistant_message_without_final_result_is_incomplete(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Starting the task."}]
                    },
                }
            ]
        )

        turn = CodeBuddyDriver().parse_turn(_response(output))

        assert not turn.completed
        assert turn.response == "Starting the task."

    def test_error_result_does_not_use_an_earlier_assistant_message(self) -> None:
        output = json.dumps(
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Starting the task."}]
                    },
                },
                {"type": "result", "subtype": "error", "is_error": True},
            ]
        )

        turn = CodeBuddyDriver().parse_turn(_response(output))

        assert not turn.completed


def _response(stdout: str) -> StdioResponse:
    return StdioResponse(stdout=stdout, stderr="", returncode=0, duration_seconds=1.0)
