"""Shared configuration models for security-oriented Agent test cases."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SecurityIdentitySettings:
    a_token: str = field(repr=False)
    a_user_id: str
    a_instance_id: str
    b_user_id: str
    b_instance_id: str

    @classmethod
    def from_environment(cls) -> SecurityIdentitySettings:
        names = (
            "AGENT_TEST_A_TOKEN",
            "AGENT_TEST_A_USER_ID",
            "AGENT_TEST_A_INSTANCE_ID",
            "AGENT_TEST_B_USER_ID",
            "AGENT_TEST_B_INSTANCE_ID",
        )
        values = {name: os.environ.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"缺少显式安全测试配置：{', '.join(missing)}")
        return cls(
            a_token=values["AGENT_TEST_A_TOKEN"],
            a_user_id=values["AGENT_TEST_A_USER_ID"],
            a_instance_id=values["AGENT_TEST_A_INSTANCE_ID"],
            b_user_id=values["AGENT_TEST_B_USER_ID"],
            b_instance_id=values["AGENT_TEST_B_INSTANCE_ID"],
        )
