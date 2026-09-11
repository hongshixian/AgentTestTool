"""Only reviewed, unchanged case implementations may enter parallel workers."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).with_name("parallel_cases.json")


@lru_cache(maxsize=None)
def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def case_execution_policy(path: Path) -> tuple[str, str]:
    """Fail closed on unknown cases or changes to a reviewed dependency."""
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
        manifest = _manifest()
        case = manifest["cases"].get(relative)
        if case is None:
            return "exclusive", "Case has not been reviewed for parallel execution"
        dependencies = {relative: case["sha256"], **manifest["dependencies"]}
        for name in manifest["groups"][case["group"]]:
            dependencies[name] = manifest["scenario_dependencies"][name]
        if any(_digest(ROOT / name) != digest for name, digest in dependencies.items()):
            return "exclusive", "Reviewed implementation changed; parallel review required"
        return "isolated", case["reason"]
    except (OSError, ValueError, KeyError, TypeError):
        return "exclusive", "Parallel review manifest unavailable or invalid"
