"""Load local environment variables without adding a runtime dependency."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path


_SENSITIVE_NAME = re.compile(r"(?:^|_)(?:API_KEY|TOKEN|PASSWORD|SECRET)(?:_|$)", re.IGNORECASE)


def sensitive_environment_values(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Collect nonblank credential-like values without reading configuration files.

    Name matching is conservative and best-effort, not a guarantee that arbitrary
    environment variables contain no secrets. Returned values are for in-memory
    redaction setup only and must not themselves be logged or persisted.
    """
    source = os.environ if environ is None else environ
    return tuple(dict.fromkeys(value for name, value in source.items()
                               if _SENSITIVE_NAME.search(name) and value.strip()))


def agent_process_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy the environment excluding Judge and test-orchestration configuration.

    Product authentication and ordinary system variables intentionally remain.
    This limits accidental inheritance; it is neither an OS sandbox nor complete
    secret isolation from a target process that can access other host resources.
    """
    source = os.environ if environ is None else environ
    return {name: value for name, value in source.items()
            if not name.upper().startswith(("JUDGE_", "AGENT_TEST_"))}


def load_project_environment(path: Path = Path(".env")) -> None:
    """Load unset variables from the project-local dotenv file."""

    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        os.environ.setdefault(name, value)
