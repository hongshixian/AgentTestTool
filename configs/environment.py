"""Load local environment variables without adding a runtime dependency."""

from __future__ import annotations

import os
from pathlib import Path


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
