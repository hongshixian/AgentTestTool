"""Verify retry handling for malformed Judge responses."""

from assertions.judge.model import JudgeConfig, OpenAICompatibleJudge


class TestJudgeRetry:
    def test_retries_invalid_json_response(self, monkeypatch) -> None:
        judge = OpenAICompatibleJudge(
            JudgeConfig(base_url="https://invalid.example", api_key="invalid")
        )
        responses = iter(("", '{"passed": true, "reason": "valid"}'))
        monkeypatch.setattr(
            judge,
            "_request_content",
            lambda messages, max_tokens: next(responses),
        )

        result = judge._request([], max_tokens=32)

        assert result == {"passed": True, "reason": "valid"}
