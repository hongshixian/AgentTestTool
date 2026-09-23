"""Offline regression checks for pinned OpenCode white-box source probes."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from agent_models.opencode.whitebox import (
    OpenCodeWhiteBoxHarness,
    WhiteBoxBindingError,
)


PERMISSION_SOURCE = """\
export function evaluate(permission: string, pattern: string, ...rulesets: PermissionV1.Ruleset[]): PermissionV1.Rule {
  return (
    rulesets
      .flat()
      .findLast((rule) => Wildcard.match(permission, rule.permission) && Wildcard.match(pattern, rule.pattern)) ?? {
      action: "ask",
      permission,
      pattern: "*",
    }
  )
}

export class Service {}

function* ask(rules) {
  for (const rule of rules) {
    if (rule.action === "deny") throw Error("denied")
    if (rule.action === "allow") continue
  }
}
"""

WILDCARD_SOURCE = """\
export * as Wildcard from "./wildcard"

export function match(input: string, pattern: string) {
  const normalized = input.replaceAll("\\\\", "/")
  let escaped = pattern
    .replaceAll("\\\\", "/")
    .replace(/[.+^${}()|[\\]\\\\]/g, "\\\\$&")
    .replace(/\\*/g, ".*")
    .replace(/\\?/g, ".")

  if (escaped.endsWith(" .*")) escaped = escaped.slice(0, -3) + "( .*)?"

  return new RegExp("^" + escaped + "$", process.platform === "win32" ? "si" : "s").test(normalized)
}
"""

DISPATCH_SOURCE = """\
const context = () => ({
  ask: (req) => permission.ask(req),
})
const tools = {
  execute(args, options) {
    const ctx = context(args, options)
    const result = yield* item.execute(args, ctx)
    return result
  },
}
"""

WRITE_SOURCE = """\
function* execute() {
  yield* ctx.ask({ permission: "edit" })
  yield* fs.writeWithDirs(filepath, content)
}
"""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def source_root(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    root = tmp_path / "source"
    originals = {
        "packages/opencode/package.json": json.dumps({"version": "1.18.32"}),
        "packages/opencode/src/permission/index.ts": PERMISSION_SOURCE,
        "packages/core/src/util/wildcard.ts": WILDCARD_SOURCE,
        "packages/opencode/src/session/tools.ts": DISPATCH_SOURCE,
        "packages/opencode/src/tool/write.ts": WRITE_SOURCE,
    }
    for name, text in originals.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    cli = tmp_path / "version.py"
    cli.write_text("print('1.18.32')\n", encoding="utf-8")
    return root, {name: _sha(text.encode("utf-8")) for name, text in originals.items()}, cli


def _harness(source_root: tuple[Path, dict[str, str], Path]) -> OpenCodeWhiteBoxHarness:
    root, hashes, cli = source_root
    return OpenCodeWhiteBoxHarness(
        root, cli_command=(sys.executable, str(cli)),
        binary_path=cli, expected_hashes=hashes,
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for OpenCode source probes")
def test_permission_probe_executes_pinned_source_with_spy(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    probe = _harness(source_root).probe_permission_rule()

    assert probe.binding.installed_version == "1.18.32"
    assert probe.binding.source_hashes == source_root[1]
    assert probe.binding.installed_binary_sha256 == _sha(source_root[2].read_bytes())
    assert probe.observed_decisions == {"allow", "deny", "ask", "error"}
    assert [item.get("action", item.get("error")) for item in probe.observations] == [
        "allow", "deny", "ask", "TypeError",
    ]
    assert all(item["wildcard_calls"] for item in probe.observations)
    assert "real tool dispatcher entry and executor Spy" in probe.missing_for_w062


def test_w062_source_boundary_requires_real_dispatch_and_build_evidence(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    mapping = _harness(source_root).map_permission_dispatch_boundary()

    assert mapping.locations["dispatcher_executor"].endswith("session/tools.ts:7")
    assert mapping.locations["write_permission"].endswith("tool/write.ts:2")
    assert mapping.locations["write_side_effect"].endswith("tool/write.ts:3")
    assert "production dispatcher execution" in mapping.missing_for_w062[1]
    assert "allow/deny/not_listed/error" in mapping.missing_for_w062[2]


def test_w062_source_boundary_rejects_unmapped_or_unpinned_dispatcher(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source_root
    path = root / "packages/opencode/src/session/tools.ts"
    path.write_text(path.read_text().replace("item.execute(args, ctx)", "invoke(args, ctx)"))
    with pytest.raises(WhiteBoxBindingError, match="Source digest mismatch"):
        _harness(source_root).map_permission_dispatch_boundary()

    hashes["packages/opencode/src/session/tools.ts"] = _sha(path.read_bytes())
    with pytest.raises(WhiteBoxBindingError, match="Production source boundary is ambiguous"):
        _harness(source_root).map_permission_dispatch_boundary()


def test_mutated_source_fails_closed(source_root: tuple[Path, dict[str, str], Path]) -> None:
    root = source_root[0]
    file = root / "packages/opencode/src/permission/index.ts"
    file.write_text(file.read_text().replace('action: "ask"', 'action: "allow"'))

    with pytest.raises(WhiteBoxBindingError, match="Source digest mismatch"):
        _harness(source_root).bind()


def test_wrong_installed_version_fails_closed(source_root: tuple[Path, dict[str, str], Path]) -> None:
    _, _, cli = source_root
    cli.write_text("print('1.18.31')\n", encoding="utf-8")

    with pytest.raises(WhiteBoxBindingError, match="Installed OpenCode version"):
        _harness(source_root).bind()


def test_wrong_package_version_even_with_matching_digest_is_rejected(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source_root
    manifest = root / "packages/opencode/package.json"
    manifest.write_text(json.dumps({"version": "1.17.0"}))
    hashes["packages/opencode/package.json"] = _sha(manifest.read_bytes())

    with pytest.raises(WhiteBoxBindingError, match="Source package version"):
        _harness(source_root).bind()


def test_source_path_symlink_cannot_escape_checkout(
    source_root: tuple[Path, dict[str, str], Path], tmp_path: Path,
) -> None:
    root, hashes, _ = source_root
    original = root / "packages/core/src/util/wildcard.ts"
    outside = tmp_path / "outside.ts"
    outside.write_bytes(original.read_bytes())
    original.unlink()
    try:
        original.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this platform")

    with pytest.raises(WhiteBoxBindingError, match="escapes checkout"):
        _harness(source_root).bind()


def test_two_builds_are_reproducible_and_distinct_from_installed_binary(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    evidence = _harness(source_root).reproduce_build(
        command=(sys.executable, "-c", "open('build.bin', 'wb').write(b'fixed-build')"),
        artifact="build.bin", timeout=10,
    )

    assert evidence.repetitions == 2
    assert evidence.artifact_sha256 == _sha(b"fixed-build")
    assert not evidence.matches_installed_binary


def test_nonreproducible_build_is_not_certified(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    with pytest.raises(WhiteBoxBindingError, match="different artifacts"):
        _harness(source_root).reproduce_build(
            command=(sys.executable, "-c", "import os;open('build.bin','wb').write(os.urandom(8))"),
            artifact="build.bin", timeout=10,
        )


def test_build_fails_closed_on_nonzero_status(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    with pytest.raises(WhiteBoxBindingError, match="Source build failed"):
        _harness(source_root).reproduce_build(
            command=(sys.executable, "-c", "import sys;sys.exit(3)"),
            artifact="build.bin", timeout=10,
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for OpenCode source probes")
def test_unexpected_permission_branch_fails_closed(
    source_root: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source_root
    file = root / "packages/opencode/src/permission/index.ts"
    file.write_text(file.read_text().replace('action: "ask"', 'action: "allow"'))
    hashes["packages/opencode/src/permission/index.ts"] = _sha(file.read_bytes())

    with pytest.raises(WhiteBoxBindingError, match="behavior differs"):
        _harness(source_root).probe_permission_rule()
