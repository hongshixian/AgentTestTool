"""Verify default and smoke pytest execution modes."""

from __future__ import annotations

from argparse import ArgumentTypeError
from dataclasses import dataclass, field

import pytest

from test_cases.conftest import (
    _positive_repeat_count,
    pytest_collection_modifyitems,
    pytest_generate_tests,
)


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


@dataclass
class _RepeatConfigStub:
    repeat_count: int

    def getoption(self, name: str) -> int:
        assert name == "--repeat"
        return self.repeat_count


@dataclass
class _MetaFuncStub:
    repeat_count: int
    fixturenames: tuple[str, ...] = ("repeat_index",)
    parameter_name: str | None = None
    parameter_values: list[int] = field(default_factory=list)
    parameter_ids: list[str] = field(default_factory=list)

    @property
    def config(self) -> _RepeatConfigStub:
        return _RepeatConfigStub(self.repeat_count)

    def parametrize(
        self,
        name: str,
        values: object,
        *,
        ids: list[str],
    ) -> None:
        self.parameter_name = name
        self.parameter_values = list(values)  # type: ignore[arg-type]
        self.parameter_ids = ids


class TestPytestExecutionMode:
    @pytest.mark.parametrize("value", ["0", "-1", "invalid"])
    def test_repeat_count_must_be_a_positive_integer(self, value: str) -> None:
        with pytest.raises(ArgumentTypeError, match="--repeat 必须是正整数"):
            _positive_repeat_count(value)

    def test_default_repeat_count_generates_one_execution(self) -> None:
        metafunc = _MetaFuncStub(repeat_count=1)

        pytest_generate_tests(metafunc)  # type: ignore[arg-type]

        assert metafunc.parameter_name == "repeat_index"
        assert metafunc.parameter_values == [1]
        assert metafunc.parameter_ids == ["repeat-1"]

    def test_requested_repeat_count_generates_each_execution(self) -> None:
        metafunc = _MetaFuncStub(repeat_count=3)

        pytest_generate_tests(metafunc)  # type: ignore[arg-type]

        assert metafunc.parameter_values == [1, 2, 3]
        assert metafunc.parameter_ids == ["repeat-1", "repeat-2", "repeat-3"]

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
