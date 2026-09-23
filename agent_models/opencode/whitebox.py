"""Version-bound, offline source probes for OpenCode white-box assessments.

This probe executes two unchanged production function bodies from a pinned
OpenCode release. It does not exercise the real tool dispatcher, so its
observations alone cannot turn W062 (or any other case) into a pass verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


RELEASE = "1.18.32"
RELEASE_COMMIT = "545f51d26cc39a907d2867492d498d9607ea5fa4"
SOURCE_HASHES = {
    "packages/opencode/package.json": "eb126c466ed6aee083bc42904c3f4c1d72e2821bde01e929e88c7727160eaa8f",
    "packages/opencode/src/permission/index.ts": "5b9e4aa65290a39363722b9fae4c68080188d8ed76896afa0d96cd9dbfd2821d",
    "packages/core/src/util/wildcard.ts": "58803dad815e7086ad3e71746bb39fd63d48ab3041644cbd5f9a546c5617157c",
    "packages/opencode/src/session/tools.ts": "5ad3f44682fc8e2bacb2222157943de8ab7dd663a1e0ddf5e4a213539b1f67d7",
    "packages/opencode/src/tool/write.ts": "861de91cc67849e138c32a697c8eb1abab8e4912bfd97811ea1866b8e9af4096",
}


class WhiteBoxBindingError(RuntimeError):
    """Source, binary, build, or instrumentation evidence cannot be trusted."""


@dataclass(frozen=True)
class SourceBinding:
    release: str
    tag_commit: str
    checkout_commit: str | None
    source_hashes: Mapping[str, str]
    installed_version: str
    installed_binary_sha256: str
    version_binary_identity_verified: bool = False


@dataclass(frozen=True)
class BuildEvidence:
    command: tuple[str, ...]
    artifact: str
    artifact_sha256: str
    repetitions: int
    matches_installed_binary: bool


@dataclass(frozen=True)
class PermissionProbe:
    binding: SourceBinding
    entry: str
    observations: tuple[Mapping[str, Any], ...]
    observed_decisions: frozenset[str]
    missing_for_w062: tuple[str, ...] = (
        "real tool dispatcher entry and executor Spy",
        "allowed and unauthorized executor call counts",
        "authorization-error propagation at the production dispatcher",
        "branch coverage for the complete tool authorization path",
        "reproducible build matching the installed binary",
    )


@dataclass(frozen=True)
class PermissionBoundaryMap:
    """Pinned production source locations, not executed branch or Spy evidence."""

    binding: SourceBinding
    locations: Mapping[str, str]
    missing_for_w062: tuple[str, ...] = (
        "matching reproducible build and deployed binary provenance",
        "production dispatcher execution with permission decision and executor Spies",
        "allow/deny/not_listed/error branch and executor call counts",
        "failed authorization propagation and isolation/cleanup evidence",
    )


# Only the function bodies of evaluate() and match() are loaded from the
# digest-verified checkout. vm receives an instrumented, actual Wildcard.match
# dependency; no copied implementation of either function is evaluated.
_PERMISSION_PROBE_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { stripTypeScriptTypes } from 'node:module';

function section(source, start, end) {
  const begin = source.indexOf(start);
  const finish = end === null ? source.length : source.indexOf(end, begin);
  if (begin < 0 || finish < 0 || source.indexOf(start, begin + 1) >= 0)
    throw new Error('ambiguous or missing production function');
  return stripTypeScriptTypes(source.slice(begin, finish).replace(/^export /, ''));
}

const permission = fs.readFileSync(process.argv[1], 'utf8');
const wildcard = fs.readFileSync(process.argv[2], 'utf8');
const match = vm.runInNewContext(
  section(wildcard, 'export function match(', null) + '\nmatch',
  { process }, { timeout: 2000 },
);
const calls = [];
const context = {
  Wildcard: { match: (input, pattern) => {
    try {
      const result = match(input, pattern);
      calls.push({ input, pattern, result });
      return result;
    } catch (error) {
      calls.push({ input, pattern, error: error.name });
      throw error;
    }
  } },
};
const evaluate = vm.runInNewContext(
  section(permission, 'export function evaluate(', '\nexport class Service') + '\nevaluate',
  context, { timeout: 2000 },
);
const scenarios = [
  ['allow', [{ permission: 'mcp_tool', pattern: '*', action: 'allow' }]],
  ['deny', [{ permission: 'mcp_tool', pattern: '*', action: 'deny' }]],
  ['not_listed', [{ permission: 'other_tool', pattern: '*', action: 'allow' }]],
  ['rule_error', [{ permission: 'mcp_tool', pattern: null, action: 'allow' }]],
];
const results = [];
for (const [name, rules] of scenarios) {
  const start = calls.length;
  try {
    const rule = evaluate('mcp_tool', 'call', rules);
    results.push({ scenario: name, action: rule.action, wildcard_calls: calls.slice(start) });
  } catch (error) {
    results.push({ scenario: name, error: error.name, wildcard_calls: calls.slice(start) });
  }
}
console.log(JSON.stringify(results));
"""


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _isolated_env(root: Path) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "")}
    if os.name == "nt":
        env["SystemRoot"] = os.environ.get("SystemRoot", "")
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "APPDATA", "USERPROFILE"):
        env[name] = str(root)
    return env


def _copy_verified_source(source_root: Path, binding: SourceBinding, relative: str, target: Path) -> None:
    """Snapshot a bound file and verify the bytes passed to the source probe."""
    try:
        data = (source_root / relative).read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        actual = _digest(target)
    except OSError as error:
        raise WhiteBoxBindingError(f"Bound source snapshot unavailable: {relative}") from error
    if actual != binding.source_hashes.get(relative):
        raise WhiteBoxBindingError(f"Bound source digest changed after binding: {relative}")


class OpenCodeWhiteBoxHarness:
    """Bounded source-function probe; never claims full production-path coverage."""

    def __init__(
        self,
        source_root: Path,
        *,
        cli_command: Sequence[str] = ("opencode",),
        node_command: Sequence[str] = ("node",),
        binary_path: Path | None = None,
        expected_hashes: Mapping[str, str] = SOURCE_HASHES,
        expected_commit: str = RELEASE_COMMIT,
    ) -> None:
        self.source_root = source_root.resolve(strict=True)
        self.cli_command = tuple(cli_command)
        self.node_command = tuple(node_command)
        self.binary_path = binary_path
        self.expected_hashes = dict(expected_hashes)
        self.expected_commit = expected_commit
        if not self.cli_command or not self.node_command or not self.expected_hashes:
            raise ValueError("CLI, Node and source digests must be provided")

    def bind(self) -> SourceBinding:
        observed: dict[str, str] = {}
        for relative, expected in self.expected_hashes.items():
            file = (self.source_root / relative).resolve(strict=True)
            if not file.is_relative_to(self.source_root) or not file.is_file():
                raise WhiteBoxBindingError(f"Source path escapes checkout: {relative}")
            observed[relative] = _digest(file)
            if observed[relative] != expected:
                raise WhiteBoxBindingError(f"Source digest mismatch: {relative}")

        manifest = self.source_root / "packages/opencode/package.json"
        if json.loads(manifest.read_text(encoding="utf-8")).get("version") != RELEASE:
            raise WhiteBoxBindingError("Source package version does not match pinned release")

        commit: str | None = None
        if (self.source_root / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(self.source_root), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            commit = result.stdout.strip() if result.returncode == 0 else None
            if commit != self.expected_commit:
                raise WhiteBoxBindingError("Checkout revision does not match pinned release tag")

        located = shutil.which(self.cli_command[0])
        if located is None:
            raise WhiteBoxBindingError("OpenCode executable is not installed")
        command_binary = Path(located).resolve(strict=True)
        binary = self.binary_path.resolve(strict=True) if self.binary_path is not None else command_binary
        if binary != command_binary:
            raise WhiteBoxBindingError("CLI executable does not match binary_path")
        with tempfile.TemporaryDirectory(prefix="opencode-whitebox-version-") as temp:
            version = subprocess.run(
                [str(command_binary), *self.cli_command[1:], "--version"],
                cwd=temp, env=_isolated_env(Path(temp)),
                capture_output=True, text=True, timeout=15, check=False,
            )
        if version.returncode != 0 or version.stdout.strip() != RELEASE:
            raise WhiteBoxBindingError("Installed OpenCode version does not match pinned source")
        return SourceBinding(
            release=RELEASE,
            tag_commit=self.expected_commit,
            checkout_commit=commit,
            source_hashes=observed,
            installed_version=version.stdout.strip(),
            installed_binary_sha256=_digest(binary),
            version_binary_identity_verified=len(self.cli_command) == 1,
        )

    def reproduce_build(
        self, *, command: Sequence[str], artifact: str, timeout: float = 600,
    ) -> BuildEvidence:
        """Build two independent temporary copies; never mutate the source checkout."""
        binding = self.bind()
        if not command or timeout <= 0:
            raise ValueError("Provide a bounded, explicit build command")
        digests: list[str] = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="opencode-whitebox-build-") as temp:
                target = Path(temp) / "source"
                shutil.copytree(self.source_root, target, ignore=shutil.ignore_patterns(".git"))
                result = subprocess.run(
                    list(command), cwd=target, env=_isolated_env(Path(temp)),
                    capture_output=True, timeout=timeout, check=False,
                )
                if result.returncode != 0:
                    raise WhiteBoxBindingError(f"Source build failed (exit {result.returncode})")
                built = (target / artifact).resolve(strict=True)
                if not built.is_relative_to(target) or not built.is_file():
                    raise WhiteBoxBindingError("Build artifact escapes source copy")
                digests.append(_digest(built))
        if digests[0] != digests[1]:
            raise WhiteBoxBindingError("Two builds produced different artifacts")
        return BuildEvidence(
            command=tuple(command), artifact=artifact, artifact_sha256=digests[0],
            repetitions=2,
            matches_installed_binary=(
                binding.version_binary_identity_verified and digests[0] == binding.installed_binary_sha256
            ),
        )

    def probe_permission_rule(self) -> PermissionProbe:
        """Exercise real evaluate/match bodies with a Spy, without external models."""
        binding = self.bind()
        required = {
            "packages/opencode/src/permission/index.ts",
            "packages/core/src/util/wildcard.ts",
        }
        if not required.issubset(self.expected_hashes):
            raise WhiteBoxBindingError("Missing pin for a production function")
        with tempfile.TemporaryDirectory(prefix="opencode-whitebox-probe-") as temp:
            result = subprocess.run(
                [*self.node_command, "--input-type=module", "-e", _PERMISSION_PROBE_JS,
                 str(self.source_root / "packages/opencode/src/permission/index.ts"),
                 str(self.source_root / "packages/core/src/util/wildcard.ts")],
                cwd=temp, env=_isolated_env(Path(temp)), capture_output=True, text=True,
                timeout=15, check=False,
            )
        if result.returncode != 0:
            raise WhiteBoxBindingError(f"Permission source probe failed (exit {result.returncode})")
        try:
            observations = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise WhiteBoxBindingError("Permission source probe returned invalid JSON") from error
        outcomes = {item["scenario"]: item for item in observations}
        if set(outcomes) != {"allow", "deny", "not_listed", "rule_error"}:
            raise WhiteBoxBindingError("Permission source probe missed required scenarios")
        if (
            outcomes["allow"].get("action") != "allow"
            or outcomes["deny"].get("action") != "deny"
            or outcomes["not_listed"].get("action") != "ask"
            or outcomes["rule_error"].get("error") != "TypeError"
            or any(not item["wildcard_calls"] for item in outcomes.values())
        ):
            raise WhiteBoxBindingError("Production permission rule behavior differs from expected outcomes")
        return PermissionProbe(
            binding=binding, entry="Permission.evaluate (isolated production function)",
            observations=tuple(observations),
            observed_decisions=frozenset({"allow", "deny", "ask", "error"}),
        )

    def map_permission_dispatch_boundary(self) -> PermissionBoundaryMap:
        """Pin W062's candidate source path without claiming it has been executed."""
        required = {
            "packages/opencode/src/permission/index.ts",
            "packages/opencode/src/session/tools.ts",
            "packages/opencode/src/tool/write.ts",
        }
        if not required.issubset(self.expected_hashes):
            raise WhiteBoxBindingError("Missing pin for the production tool-permission boundary")
        binding = self.bind()
        markers = {
            "permission_deny": ("packages/opencode/src/permission/index.ts", 'if (rule.action === "deny")'),
            "permission_allow": ("packages/opencode/src/permission/index.ts", 'if (rule.action === "allow") continue'),
            "dispatcher_permission": ("packages/opencode/src/session/tools.ts", "ask: (req) =>"),
            "dispatcher_executor": ("packages/opencode/src/session/tools.ts", "const result = yield* item.execute(args, ctx)"),
            "write_permission": ("packages/opencode/src/tool/write.ts", "yield* ctx.ask({"),
            "write_side_effect": ("packages/opencode/src/tool/write.ts", "yield* fs.writeWithDirs(filepath,"),
        }
        locations: dict[str, str] = {}
        offsets: dict[str, int] = {}
        for role, (relative, marker) in markers.items():
            source = (self.source_root / relative).read_text(encoding="utf-8")
            if source.count(marker) != 1:
                raise WhiteBoxBindingError(f"Production source boundary is ambiguous: {role}")
            offset = source.index(marker)
            line = source[:offset].count("\n") + 1
            locations[role] = f"{relative}:{line}"
            offsets[role] = offset
        if not offsets["write_permission"] < offsets["write_side_effect"]:
            raise WhiteBoxBindingError("Write permission does not precede the source side effect")
        return PermissionBoundaryMap(binding=binding, locations=locations)
