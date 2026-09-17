"""Verify pytest only starts network capture for executable black-box cases."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from test_cases import conftest as case_conftest
from test_cases.conftest import _item_requires_network_capture


def test_operator_evidence_case_does_not_start_network_capture():
    item = SimpleNamespace(
        module=SimpleNamespace(
            OPERATOR_EVIDENCE_REQUIRED=True,
            IMPLEMENTATION_MODE="p2_proxy",
        ),
    )

    assert not _item_requires_network_capture(item)


def test_deferred_case_does_not_start_network_capture():
    item = SimpleNamespace(
        module=SimpleNamespace(IMPLEMENTATION_MODE=" deferred "),
    )

    assert not _item_requires_network_capture(item)


def test_agent_trace_case_starts_network_capture():
    item = SimpleNamespace(
        module=SimpleNamespace(IMPLEMENTATION_MODE="p2_proxy"),
    )

    assert _item_requires_network_capture(item)


def test_case_without_classification_starts_network_capture():
    item = SimpleNamespace(module=SimpleNamespace())

    assert _item_requires_network_capture(item)


def test_black_box_case_never_starts_network_capture():
    item = SimpleNamespace(
        module=SimpleNamespace(TEST_CASE_ID="B001", TEST_CASE_LEVEL="black_box"),
        keywords={"e2e": True, "black_box": True},
    )

    assert not _item_requires_network_capture(item)


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        (SimpleNamespace(IMPLEMENTATION_MODE="deferred"), False),
        (SimpleNamespace(OPERATOR_EVIDENCE_REQUIRED=True), False),
        (SimpleNamespace(IMPLEMENTATION_MODE="p2_proxy"), True),
    ],
)
def test_agent_model_fixture_passes_capture_selection_to_factory(
    tmp_path,
    monkeypatch,
    module,
    expected,
):
    captured = {}

    class _Ledger:
        def record(self, *_args, **_kwargs):
            return None

        def save_artifact(self, *_args, **_kwargs):
            return None

    @contextmanager
    def create(*_args, **kwargs):
        captured.update(kwargs)
        yield SimpleNamespace(
            environment=SimpleNamespace(
                evidence_directory=tmp_path / "evidence" / "run",
                ledger=_Ledger(),
            )
        )

    monkeypatch.setattr(case_conftest.AgentModelFactory, "create", create)
    node = SimpleNamespace(
        nodeid="offline-capture-selection",
        module=module,
        stash=pytest.Stash(),
        user_properties=[],
    )
    config = SimpleNamespace(
        getoption=lambda name: {
            "--agent": "codebuddy",
            "--evidence-dir": str(tmp_path / "evidence"),
        }[name]
    )
    fixture = case_conftest.agent_model.__wrapped__(
        SimpleNamespace(node=node, config=config),
        tmp_path / "workspace",
    )

    next(fixture)
    with pytest.raises(StopIteration):
        next(fixture)

    assert captured["enable_network_capture"] is expected
