"""Pinned OpenClaw release, test model and credential sources."""

from __future__ import annotations

import os
from dataclasses import dataclass

EXPECTED_VERSION = "2026.8.35"
DEFAULT_TEST_MODEL = "infi/glm-5.3-flash"
DEFAULT_BASE_URL = "https://router.ai.iiis.co:9443/v1"
PROVIDER_ID = "iiis"


@dataclass(frozen=True, slots=True)
class OpenClawTestProfile:
    """Everything needed to build one private OpenClaw configuration."""

    executable: str = "openclaw"
    model: str = DEFAULT_TEST_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    expected_version: str = EXPECTED_VERSION

    @classmethod
    def from_environment(cls) -> OpenClawTestProfile:
        return cls(
            executable=os.environ.get("OPENCLAW_BIN", "").strip() or "openclaw",
            model=os.environ.get("OPENCLAW_TEST_MODEL", "").strip() or DEFAULT_TEST_MODEL,
            base_url=os.environ.get("OPENCLAW_TEST_BASE_URL", "").strip() or DEFAULT_BASE_URL,
            api_key=(os.environ.get("OPENCLAW_TEST_API_KEY", "").strip()
                     or os.environ.get("IIIS_API_KEY", "").strip()),
        )

    @property
    def model_ref(self) -> str:
        return f"{PROVIDER_ID}/{self.model}"

    @property
    def secrets(self) -> tuple[str, ...]:
        return (self.api_key,) if self.api_key else ()
