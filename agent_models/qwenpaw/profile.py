"""Dedicated QwenPaw test configuration, read only from explicit environment settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

EXPECTED_VERSION = "2.2.1"
DEFAULT_PROVIDER_ID = "iiis"
DEFAULT_PROVIDER_NAME = "IIIS LiteLLM"
DEFAULT_BASE_URL = "https://router.ai.iiis.co:9443/v1"
DEFAULT_TEST_MODEL = "infi/glm-5.3-flash"


@dataclass(frozen=True, slots=True)
class QwenPawTestProfile:
    """Settings for one isolated QwenPaw instance.

    The API key reaches QwenPaw only through its loopback REST configuration
    endpoint; it is never placed in the product's process environment or argv.
    """

    executable: str = "qwenpaw"
    provider_id: str = DEFAULT_PROVIDER_ID
    provider_name: str = DEFAULT_PROVIDER_NAME
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_TEST_MODEL
    api_key: str = ""
    expected_version: str = EXPECTED_VERSION

    @classmethod
    def from_environment(cls) -> QwenPawTestProfile:
        def setting(name: str, default: str) -> str:
            return os.environ.get(name, "").strip() or default

        return cls(
            executable=setting("QWENPAW_BIN", "qwenpaw"),
            base_url=setting("QWENPAW_TEST_BASE_URL", DEFAULT_BASE_URL),
            model=setting("QWENPAW_TEST_MODEL", DEFAULT_TEST_MODEL),
            api_key=(os.environ.get("QWENPAW_TEST_API_KEY", "").strip()
                     or os.environ.get("IIIS_API_KEY", "").strip()),
        )

    @property
    def secrets(self) -> tuple[str, ...]:
        return (self.api_key,) if self.api_key else ()
