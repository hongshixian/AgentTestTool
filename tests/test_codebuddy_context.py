"""Verify CodeBuddy request-context header mapping."""

from __future__ import annotations

import pytest

from agent_models import RequestContext
from agent_models.codebuddy.context import CodeBuddyRequestContextAdapter


class TestCodeBuddyRequestContextAdapter:
    def test_omits_instance_header_for_null_boundary(self) -> None:
        adapter = _adapter()
        context = RequestContext("Bearer test", "user-a", None, "run-1")

        args = adapter.extra_args(context)

        assert args == (
            "--header",
            "X-Test-User-ID: user-a",
            "X-Test-Run-ID: run-1",
        )

    def test_preserves_oversized_instance_boundary(self) -> None:
        adapter = _adapter()
        instance_id = "A" * 8192
        context = RequestContext("Bearer test", "user-a", instance_id, "run-1")

        args = adapter.extra_args(context)

        assert args[-1] == f"X-Test-Instance-ID: {instance_id}"

    def test_rejects_header_value_injection(self) -> None:
        adapter = _adapter()
        context = RequestContext("Bearer test", "user-a\nInjected: yes", "instance-a", "run-1")

        with pytest.raises(ValueError, match="换行符"):
            adapter.extra_args(context)


def _adapter() -> CodeBuddyRequestContextAdapter:
    return CodeBuddyRequestContextAdapter(
        {
            "user_id": "X-Test-User-ID",
            "instance_id": "X-Test-Instance-ID",
            "run_id": "X-Test-Run-ID",
        }
    )
