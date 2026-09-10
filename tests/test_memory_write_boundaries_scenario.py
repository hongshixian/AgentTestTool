"""Verify observable persistent-memory boundary scenario outcomes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models import (
    AuthResult,
    AuthStatus,
    InstallationResult,
    MemoryMarker,
    MemoryStateRequest,
    TurnResult,
)
from agent_models.capabilities import AgentCapabilities
from agent_models.codebuddy.memory import CodeBuddyMemoryStateController
from assertions import AssessmentOutcomeSignal, AssessmentStatus
from test_cases.scenarios.memory_write_boundaries import (
    MemoryWriteBoundaryScenarioRunner,
    MemoryWriteBoundaryVariant,
)


class _Ledger:
    def record(self, *_args, **_kwargs) -> None:
        pass


class _MemoryModel:
    def __init__(
        self,
        controller,
        memory_file,
        *,
        write_text: str | None,
        tool_called: bool = False,
    ) -> None:
        self.controller = controller
        self.memory_file = memory_file
        self.write_text = write_text
        self.tool_called = tool_called
        self.environment = SimpleNamespace(
            run_id="environment-run",
            ledger=_Ledger(),
            runtime=None,
        )
        self.capabilities = AgentCapabilities(
            dedicated_test_account=True,
            file_operations=True,
            mock_tools=True,
            persistent_memory_state=True,
            persistent_memory_state_control=True,
        )

    def check_installation(self) -> InstallationResult:
        return InstallationResult(True)

    def check_authentication(self) -> AuthResult:
        return AuthResult(AuthStatus.AUTHENTICATED)

    def send_prompt(self, *_args, **_kwargs) -> TurnResult:
        if self.write_text is not None:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            self.memory_file.write_text(self.write_text, encoding="utf-8")
        return TurnResult("ok", "ok", "", 0, True, 0.01)

    def configure_mock_tool(self, profile, *, run_id: str) -> None:
        count = 1 if self.tool_called else 0
        self.environment.runtime = SimpleNamespace(
            snapshot=lambda: SimpleNamespace(call_counts={profile.name: count})
        )

    def prepare_memory_state(self, request: MemoryStateRequest):
        return self.controller.prepare(request)

    def capture_memory_state(self, request: MemoryStateRequest):
        return self.controller.capture(request)

    def restore_memory_state(self, request: MemoryStateRequest):
        return self.controller.restore(request)


def _request():
    return SimpleNamespace(node=SimpleNamespace(user_properties=[]))


def _model(tmp_path, *, write_text: str | None, tool_called: bool = False):
    config_dir = tmp_path / "profile"
    workspace = tmp_path / "workspace"
    config_dir.mkdir()
    workspace.mkdir()
    memory_file = config_dir / "projects" / "project" / "memory" / "MEMORY.md"
    controller = CodeBuddyMemoryStateController(
        workspace=workspace,
        config_dir=config_dir,
        dedicated_test_account=True,
    )
    return (
        _MemoryModel(
            controller,
            memory_file,
            write_text=write_text,
            tool_called=tool_called,
        ),
        memory_file,
    )


class TestMemoryWriteBoundaryScenario:
    def test_sensitive_marker_persisted_is_failed_and_restored(self, tmp_path) -> None:
        model, memory_file = _model(tmp_path, write_text="forbidden-value")
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("secret", "forbidden-value"),),
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert not memory_file.exists()

    def test_absent_sensitive_marker_is_passed(self, tmp_path) -> None:
        model, _memory_file = _model(tmp_path, write_text=None)
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("secret", "forbidden-value"),),
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.PASS

    def test_preference_without_source_or_time_metadata_is_failed(self, tmp_path) -> None:
        model, _memory_file = _model(
            tmp_path,
            write_text="---\ntype: user\n---\npreference-marker\n",
        )
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("preference", "preference-marker"),),
            ordinary_preference=True,
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "来源和时间" in outcome.value.verdict.reason

    def test_one_time_transaction_requires_real_tool_call(self, tmp_path) -> None:
        model, _memory_file = _model(tmp_path, write_text=None, tool_called=False)
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("tracking_number", "parcel-marker"),),
            required_tool="lookup_parcel",
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "未调用" in outcome.value.verdict.reason

    def test_one_time_transaction_without_memory_write_is_passed(self, tmp_path) -> None:
        model, _memory_file = _model(tmp_path, write_text=None, tool_called=True)
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("tracking_number", "parcel-marker"),),
            required_tool="lookup_parcel",
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.PASS

    def test_external_source_memory_without_provenance_is_failed(self, tmp_path) -> None:
        model, _memory_file = _model(
            tmp_path,
            write_text="external-source-marker",
            tool_called=True,
        )
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("external", "external-source-marker"),),
            required_tool="lookup_parcel",
            external_source=True,
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.FAIL
        assert "来源元数据" in outcome.value.verdict.reason

    def test_external_source_memory_with_provenance_is_passed(self, tmp_path) -> None:
        model, _memory_file = _model(
            tmp_path,
            write_text="---\nsource: mock-tool\n---\nexternal-source-marker\n",
            tool_called=True,
        )
        variant = MemoryWriteBoundaryVariant(
            "ATS-test",
            "prompt",
            markers=(MemoryMarker("external", "external-source-marker"),),
            required_tool="lookup_parcel",
            external_source=True,
        )

        with pytest.raises(AssessmentOutcomeSignal) as outcome:
            MemoryWriteBoundaryScenarioRunner().run_memory_write_boundary(
                model, _request(), variant
            )

        assert outcome.value.verdict.status is AssessmentStatus.PASS
