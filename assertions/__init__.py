"""Traditional and intelligent assertions for Agent CLI test cases."""

from assertions.logical import (
    assert_agent_authenticated,
    assert_authoritative_identity_unchanged,
    assert_protected_resources_not_accessed,
    assert_required_evidence,
    assert_turn_completed,
)

__all__ = [
    "assert_agent_authenticated",
    "assert_authoritative_identity_unchanged",
    "assert_protected_resources_not_accessed",
    "assert_required_evidence",
    "assert_turn_completed",
]
