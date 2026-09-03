"""CodeBuddy authentication-state provider."""

from __future__ import annotations

import os
from pathlib import Path

from agent_models.result import AuthResult, AuthStatus


class CodeBuddyCredentialProvider:
    """Locate the login state created by CodeBuddy's own login flow."""

    def __init__(self, config_home: Path | None = None) -> None:
        configured_home = os.environ.get("CODEBUDDY_CONFIG_HOME")
        self.config_home = config_home or (
            Path(configured_home).expanduser() if configured_home else Path.home() / ".codebuddy"
        )

    def has_local_login_state(self) -> bool:
        storage = self.config_home / "local_storage"
        return storage.is_dir() and any(storage.iterdir())

    def login(self) -> AuthResult:
        return AuthResult(
            status=AuthStatus.UNAUTHENTICATED,
            detail="请先运行 codebuddy 并使用产品登录流程完成认证",
        )

