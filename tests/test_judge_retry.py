"""Verify retry handling for malformed and transient Judge responses."""

from __future__ import annotations

import io
import urllib.error

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

    def test_retries_http_429_using_retry_after(self, monkeypatch) -> None:
        judge = OpenAICompatibleJudge(
            JudgeConfig(base_url="https://invalid.example", api_key="invalid")
        )
        error = urllib.error.HTTPError(
            "https://invalid.example/v1/chat/completions",
            429,
            "rate limited",
            {"Retry-After": "0"},
            io.BytesIO(),
        )

        class Response:
            def __enter__(self):
                return io.StringIO(
                    '{"choices":[{"message":{"content":"{\\"passed\\":true,\\"reason\\":\\"ok\\"}"}}]}'
                )

            def __exit__(self, *_args):
                return False

        responses = iter((error, Response()))

        def urlopen(*_args, **_kwargs):
            value = next(responses)
            if isinstance(value, Exception):
                raise value
            return value

        monkeypatch.setattr("assertions.judge.model.urllib.request.urlopen", urlopen)
        monkeypatch.setattr("assertions.judge.model.time.sleep", lambda _delay: None)

        assert judge._request([], max_tokens=32) == {"passed": True, "reason": "ok"}
