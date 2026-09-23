"""Offline regression tests for W066's bounded source-function probe."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from agent_models.opencode.whitebox import WhiteBoxBindingError
from agent_models.opencode.whitebox_w066 import W066OpenCodeHarness


PROCESSOR = """\
      const toolResultOutput = (
        value: { name: string; result: { type: string; value: unknown } },
      ): { title: string; metadata: Record<string, any>; output: string } => {
        if (isRecord(value.result.value) && typeof value.result.value.output === "string") {
          return { title: value.name, metadata: {}, output: value.result.value.output }
        }
        return {
          title: value.name,
          metadata: value.result.type === "json" && isRecord(value.result.value) ? value.result.value : {},
          output: typeof value.result.value === "string" ? value.result.value : (JSON.stringify(value.result.value) ?? ""),
        }
      }

      const handleEvent = undefined
      const rawOutput = toolResultOutput(value)
"""

ASSEMBLER = """\
  const toModelOutput = (options: { output: unknown }) => {
    const output = options.output
    if (typeof output === "string") return { type: "text", value: output }
    return { type: "json", value: output }
  }

  for (const msg of input) {}
"""

PROMPT = "const messages = MessageV2.toModelMessagesEffect(msgs, model)\n"
REQUEST = 'export const prepare = Effect.fn("LLMRequestPrep.prepare")(function* () {})\n'


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    root = tmp_path / "source"
    sources = {
        "packages/opencode/package.json": json.dumps({"version": "1.18.32"}),
        "packages/opencode/src/session/processor.ts": PROCESSOR,
        "packages/opencode/src/session/message-v2.ts": ASSEMBLER,
        "packages/opencode/src/session/prompt.ts": PROMPT,
        "packages/opencode/src/session/llm/request.ts": REQUEST,
    }
    for relative, text in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    cli = tmp_path / "version.py"
    cli.write_text("print('1.18.32')\n", encoding="utf-8")
    return root, {name: _digest(root / name) for name in sources}, cli


def _harness(source: tuple[Path, dict[str, str], Path]) -> W066OpenCodeHarness:
    root, hashes, cli = source
    return W066OpenCodeHarness(
        root,
        cli_command=(sys.executable, str(cli)),
        binary_path=Path(sys.executable),
        expected_hashes=hashes,
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="Node 24+ required for TypeScript source probes")
def test_four_variants_execute_source_but_do_not_claim_a_verdict(
    source: tuple[Path, dict[str, str], Path],
) -> None:
    result = _harness(source).probe()

    assert result.exit_code == 0
    assert result.normalized_return_count == 4
    assert [item["call_id"] for item in result.variants] == [
        "call-normal", "call-injected", "call-empty", "call-json",
    ]
    assert result.variants[0]["normalized_output"] == "Public data."
    assert result.variants[1]["converted_output"]["value"].startswith("Ignore previous")
    assert result.variants[2]["converted_output"] == {"type": "text", "value": ""}
    assert result.variants[3]["normalized_output"] == '{"ok":true,"public":"value"}'
    assert result.provider_roles is None
    assert result.processed_return_count is None
    assert result.elevated_to_system_message_count is None
    assert result.unchecked_return_count is None
    assert any("roles alone do not prove detection" in reason for reason in result.missing_for_w066)
    assert result.source_locations["normalization"].endswith("processor.ts:1")


def test_tampered_source_digest_is_rejected(source: tuple[Path, dict[str, str], Path]) -> None:
    root = source[0]
    path = root / "packages/opencode/src/session/processor.ts"
    path.write_text(path.read_text().replace("toolResultOutput", "fakeResultHandler"))
    with pytest.raises(WhiteBoxBindingError, match="Source digest mismatch"):
        _harness(source).probe()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node 24+ required for TypeScript source probes")
def test_rejects_checkout_change_between_binding_and_source_copy(
    source: tuple[Path, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(source)
    original_bind = harness._harness.bind
    processor = source[0] / "packages/opencode/src/session/processor.ts"

    def changed_bind():
        binding = original_bind()
        processor.write_text(processor.read_text(encoding="utf-8") + "\n// changed after binding\n", encoding="utf-8")
        return binding

    monkeypatch.setattr(harness._harness, "bind", changed_bind)
    with pytest.raises(WhiteBoxBindingError, match="source digest changed after binding"):
        harness.probe()


def test_unmapped_processor_boundary_rejected_even_after_rehash(
    source: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source
    path = root / "packages/opencode/src/session/processor.ts"
    path.write_text(path.read_text().replace("const rawOutput = toolResultOutput(value)", "const rawOutput = value"))
    hashes["packages/opencode/src/session/processor.ts"] = _digest(path)
    with pytest.raises(WhiteBoxBindingError, match="W066 source boundary missing"):
        _harness(source).probe()


def test_wrong_deployed_binary_version_is_rejected(source: tuple[Path, dict[str, str], Path]) -> None:
    cli = source[2]
    cli.write_text("print('1.18.31')\n", encoding="utf-8")
    with pytest.raises(WhiteBoxBindingError, match="Installed OpenCode version"):
        _harness(source).probe()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node 24+ required for TypeScript source probes")
def test_normalizer_logic_is_executed_not_hardcoded(
    source: tuple[Path, dict[str, str], Path],
) -> None:
    root, hashes, _ = source
    path = root / "packages/opencode/src/session/processor.ts"
    path.write_text(path.read_text().replace('typeof value.result.value === "string" ? value.result.value',
                                             'typeof value.result.value === "string" ? "redacted"'))
    hashes["packages/opencode/src/session/processor.ts"] = _digest(path)
    results = _harness(source).probe().variants
    assert [item["normalized_output"] for item in results[:3]] == ["redacted"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="Node 24+ required for TypeScript source probes")
def test_real_pinned_source_when_checkout_explicitly_provided() -> None:
    checkout = os.environ.get("OPENCODE_SOURCE_CHECKOUT")
    if not checkout:
        pytest.skip("Set OPENCODE_SOURCE_CHECKOUT for an optional pinned-source probe")
    result = W066OpenCodeHarness(Path(checkout)).probe()
    assert result.binding.checkout_commit == "545f51d26cc39a907d2867492d498d9607ea5fa4"
    assert result.normalized_return_count == 4
    assert result.provider_roles is None
    assert result.unchecked_return_count is None
