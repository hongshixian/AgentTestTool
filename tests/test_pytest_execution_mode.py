"""Verify default and smoke pytest execution modes."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from test_cases.conftest import pytest_collection_modifyitems


@dataclass
class _ConfigStub:
    smoke: bool

    def getoption(self, name: str) -> bool:
        assert name == "--smoke"
        return self.smoke


@dataclass
class _ItemStub:
    keywords: dict[str, object]
    markers: list[pytest.MarkDecorator] = field(default_factory=list)

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.markers.append(marker)


class TestPytestExecutionMode:
    def test_default_mode_does_not_skip_e2e_cases(self) -> None:
        e2e = _ItemStub({"e2e": True})

        pytest_collection_modifyitems(_ConfigStub(smoke=False), [e2e])  # type: ignore[arg-type]

        assert e2e.markers == []

    def test_smoke_mode_keeps_unit_and_smoke_e2e_cases(self) -> None:
        unit = _ItemStub({})
        smoke_e2e = _ItemStub({"e2e": True, "smoke": True})
        full_e2e = _ItemStub({"e2e": True})

        pytest_collection_modifyitems(  # type: ignore[arg-type]
            _ConfigStub(smoke=True),
            [unit, smoke_e2e, full_e2e],
        )

        assert unit.markers == []
        assert smoke_e2e.markers == []
        assert len(full_e2e.markers) == 1
        assert full_e2e.markers[0].mark.name == "skip"
        assert full_e2e.markers[0].mark.kwargs["reason"] == "smoke 模式仅执行最小 E2E 用例集"
