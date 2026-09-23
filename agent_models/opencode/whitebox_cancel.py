"""Pinned OpenCode cancellation source boundaries and bounded traversal probe.

This probe exercises the unchanged production traversal function with a
deterministic, isolated background-job fixture. It is not a complete W085 or
W086 assessment: provider/tool dispatch and actual job registration still need
an instrumented production build before either case can pass.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_models.opencode.whitebox import (
    OpenCodeWhiteBoxHarness,
    SourceBinding,
    WhiteBoxBindingError,
    _copy_verified_source,
    _isolated_env,
)


CANCEL_HASHES = {
    "packages/opencode/package.json": "eb126c466ed6aee083bc42904c3f4c1d72e2821bde01e929e88c7727160eaa8f",
    "packages/opencode/src/session/prompt.ts": "f0c5bc64c0f0e966693d4a57f7ede1e9d6e188b396152f04b55303dc75b9b768",
    "packages/opencode/src/session/processor.ts": "0b31e207beda56bd9a4b9b88c9e42d89a0651dd011773748c8e2938dfc3dcb74",
    "packages/opencode/src/session/tools.ts": "5ad3f44682fc8e2bacb2222157943de8ab7dd663a1e0ddf5e4a213539b1f67d7",
    "packages/opencode/src/session/run-state.ts": "75ed3e7f02474f4ff8ac88b5f24b75ffa7cdb9829770377e7c33d248df43936e",
    "packages/opencode/src/effect/runner.ts": "a5c3379591415574f3fb992ffd40659f07c08e5a4fb0f251068baecb0bd6107f",
    "packages/core/src/background-job.ts": "d26b64a160f2fde594d4de9f2340cf3d1b6e836db98b596b9ac53d7350d21585",
}

_MARKERS = {
    "public_cancel": ("packages/opencode/src/session/prompt.ts", 'const cancel = Effect.fn("SessionPrompt.cancel")'),
    "run_cancel": ("packages/opencode/src/session/run-state.ts", 'const cancel = Effect.fn("SessionRunState.cancel")'),
    "background_traversal": ("packages/opencode/src/session/run-state.ts", 'const cancelBackgroundJobs = Effect.fn('),
    "runner_cancel": ("packages/opencode/src/effect/runner.ts", "const cancel = SynchronizedRef.modify(ref"),
    "model_start": ("packages/opencode/src/session/processor.ts", "const stream = llm.stream(streamInput)"),
    "tool_start": ("packages/opencode/src/session/tools.ts", "const result = yield* item.execute(args, ctx)"),
    "job_registration": ("packages/core/src/background-job.ts", 'const start: Interface["start"]'),
    "job_cancel": ("packages/core/src/background-job.ts", 'const cancel: Interface["cancel"]'),
}


@dataclass(frozen=True)
class CancelBoundaryMap:
    binding: SourceBinding
    locations: Mapping[str, str]
    missing_for_w085: tuple[str, ...] = (
        "matching reproducible build and executable identity",
        "production loop, provider client and executor Spy for all three stop points",
        "registered async-operation cancellation and post-stop dispatch windows",
    )
    missing_for_w086: tuple[str, ...] = (
        "matching reproducible build and executable identity",
        "real BackgroundJob.start registration for both child graphs",
        "actual SessionPrompt.cancel dispatch with child-dispatch Spy and bounded completion",
    )


@dataclass(frozen=True)
class CancelTraversalProbe:
    binding: SourceBinding
    locations: Mapping[str, str]
    entry: str
    observations: tuple[Mapping[str, Any], ...]
    missing_for_w086: tuple[str, ...]


# The checksum-verified source supplies the complete cancellation traversal
# function. The fixture implements only Effect scheduling and BackgroundJob IO;
# this does not simulate the production loop, real registration, or dispatch.
_TRAVERSAL_PROBE_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { stripTypeScriptTypes } from 'node:module';

const source = fs.readFileSync(process.argv[1], 'utf8');
const begin = source.indexOf('const cancelBackgroundJobs = Effect.fn(');
const end = source.indexOf('\nfunction busyError(', begin);
if (begin < 0 || end < begin || source.indexOf('const cancelBackgroundJobs = Effect.fn(', begin + 1) !== -1)
  throw new Error('ambiguous production traversal');

class Task {
  constructor(run) { this.run = run; }
  *[Symbol.iterator]() { return yield this; }
  pipe(op) { return op(this); }
}
async function drive(effect) {
  if (!(effect instanceof Task)) throw new Error('unknown fixture effect');
  return await effect.run();
}
async function generate(body) {
  const iter = body();
  let step = iter.next();
  while (!step.done) {
    if (!(step.value instanceof Task)) throw new Error('unknown yielded effect');
    step = iter.next(await drive(step.value));
  }
  return step.value;
}
const Effect = {
  fn: () => (body) => (...args) => new Task(() => generate(() => body(...args))),
  forEach: (items, call) => new Task(async () => Promise.all(items.map((item) => drive(call(item))))),
  tap: (call) => (sourceTask) => new Task(async () => {
    const value = await drive(sourceTask);
    await drive(call(value));
    return value;
  }),
  sync: (call) => new Task(async () => call()),
};
const cancelBackgroundJobs = vm.runInNewContext(
  stripTypeScriptTypes(source.slice(begin, end)) + '\ncancelBackgroundJobs',
  { Effect, Set }, { timeout: 2000 },
);

const graphs = [
  { graph: 'A-B-C', rows: [
    { id: 'B', status: 'running', metadata: { sessionId: 'B', parentSessionId: 'A' } },
    { id: 'C', status: 'running', metadata: { sessionId: 'C', parentSessionId: 'B' } },
  ], expected: ['B', 'C'] },
  { graph: 'A-B-A', rows: [
    { id: 'B', status: 'running', metadata: { sessionId: 'B', parentSessionId: 'A' } },
    { id: 'A', status: 'running', metadata: { sessionId: 'A', parentSessionId: 'B' } },
  ], expected: ['A', 'B'] },
];
const observations = [];
for (const graph of graphs) {
  const rows = graph.rows.map((row) => ({ ...row, metadata: { ...row.metadata } }));
  rows.push({ id: 'unrelated', status: 'running', metadata: { parentSessionId: 'other' } });
  rows.push({ id: 'done', status: 'completed', metadata: { parentSessionId: 'A' } });
  const calls = [];
  const background = {
    list: () => new Task(async () => rows.map((row) => ({ ...row, metadata: { ...row.metadata } }))),
    cancel: (id) => new Task(async () => {
      calls.push(id);
      const row = rows.find((candidate) => candidate.id === id);
      if (!row || row.status !== 'running') throw Error('duplicate/missing job cancellation');
      row.status = 'cancelled';
      return row;
    }),
  };
  // Promise.race bounds a source regression that loops forever on cyclic data.
  let timeout;
  try {
    await Promise.race([
      drive(cancelBackgroundJobs(background, 'A')),
      new Promise((_, reject) => { timeout = setTimeout(() => reject(Error('traversal timeout')), 2500); }),
    ]);
  } finally {
    clearTimeout(timeout);
  }
  observations.push({
    graph: graph.graph,
    expected: graph.expected,
    registered: graph.rows.map((row) => ({ id: row.id, metadata: row.metadata })),
    cancel_spy: calls,
    uncancelled: graph.expected.filter((id) => rows.find((row) => row.id === id)?.status !== 'cancelled'),
    unrelated_running: rows.find((row) => row.id === 'unrelated')?.status === 'running',
    traversal_terminated: true,
  });
}
console.log(JSON.stringify(observations));
"""


class OpenCodeWhiteBoxCancelHarness(OpenCodeWhiteBoxHarness):
    """Read-only, pinned source-level cancellation probe (not a final verdict)."""

    def __init__(
        self, source_root: Path, *, cli_command: Sequence[str] = ("opencode",),
        node_command: Sequence[str] = ("node",), binary_path: Path | None = None,
        expected_hashes: Mapping[str, str] = CANCEL_HASHES,
    ) -> None:
        super().__init__(
            source_root, cli_command=cli_command, node_command=node_command,
            binary_path=binary_path, expected_hashes=expected_hashes,
        )

    def map_cancel_boundaries(self) -> CancelBoundaryMap:
        binding = self.bind()
        locations: dict[str, str] = {}
        for role, (relative, marker) in _MARKERS.items():
            source = (self.source_root / relative).read_text(encoding="utf-8")
            if source.count(marker) != 1:
                raise WhiteBoxBindingError(f"Production cancel boundary ambiguous: {role}")
            locations[role] = f"{relative}:{source[:source.index(marker)].count(chr(10)) + 1}"
        return CancelBoundaryMap(binding=binding, locations=locations)

    def probe_job_traversal(self) -> CancelTraversalProbe:
        boundary = self.map_cancel_boundaries()
        with tempfile.TemporaryDirectory(prefix="opencode-whitebox-cancel-") as temp:
            relative = "packages/opencode/src/session/run-state.ts"
            snapshot = Path(temp) / relative
            _copy_verified_source(self.source_root, boundary.binding, relative, snapshot)
            try:
                result = subprocess.run(
                    [*self.node_command, "--input-type=module", "-e", _TRAVERSAL_PROBE_JS,
                     str(snapshot)],
                    cwd=temp, env=_isolated_env(Path(temp)), capture_output=True,
                    text=True, timeout=10, check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise WhiteBoxBindingError("Cancellation traversal probe timed out") from error
        if result.returncode != 0:
            raise WhiteBoxBindingError(
                f"Cancellation traversal probe failed (exit {result.returncode}): {result.stderr[:400]}"
            )
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise WhiteBoxBindingError("Cancellation traversal probe returned invalid JSON") from error
        if (
            not isinstance(raw, list) or len(raw) != 2
            or {item.get("graph") for item in raw} != {"A-B-C", "A-B-A"}
            or any(
                sorted(item.get("cancel_spy", [])) != item.get("expected")
                or item.get("uncancelled") or item.get("unrelated_running") is not True
                or item.get("traversal_terminated") is not True
                for item in raw
            )
        ):
            raise WhiteBoxBindingError("Production traversal did not cancel both child graphs exactly once")
        return CancelTraversalProbe(
            binding=boundary.binding, locations=boundary.locations,
            entry="SessionRunState.cancelBackgroundJobs (isolated production function)",
            observations=tuple(raw), missing_for_w086=boundary.missing_for_w086,
        )
