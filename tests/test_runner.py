"""Verify the smoke-gated assessment workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_test_tool.runner import WorkflowConfig, run_workflow


def _phase_payload(statuses: list[str], *, exitstatus: int = 0) -> dict[str, object]:
    cases = [
        {
            "nodeid": f"test_cases/test_case.py::TestCase::test_case[{index}]",
            "test_case_id": f"ATS-TEST-{index}",
            "name": f"用例 {index}",
            "status": status,
            "reason": "测试原因",
            "missing_evidence": [],
            "duration_seconds": 0.1,
            "pytest_status": "passed" if status != "不通过" else "failed",
            "phases": {},
        }
        for index, status in enumerate(statuses, start=1)
    ]
    return {
        "schema_version": 1,
        "session": {
            "exitstatus": exitstatus,
            "collected": len(cases),
            "reported_cases": len(cases),
            "internal_errors": [],
            "collection_errors": [],
        },
        "cases": cases,
        "summary": {status: statuses.count(status) for status in set(statuses)},
    }


class _FakePytest:
    def __init__(self, payloads: list[dict[str, object]], returncodes: list[int]) -> None:
        self.payloads = payloads
        self.returncodes = returncodes
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        output_index = command.index("--agent-result-json") + 1
        Path(command[output_index]).write_text(
            json.dumps(self.payloads.pop(0), ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            self.returncodes.pop(0),
            stdout="pytest output",
            stderr="",
        )


def _fake_pdf(payload: object, output: Path) -> None:
    assert isinstance(payload, dict)
    output.write_bytes(b"%PDF-test")


class TestWorkflowRunner:
    def test_smoke_pass_runs_business_and_generates_report(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest(
            [_phase_payload(["通过", "通过"]), _phase_payload(["通过", "无法判定"])],
            [0, 0],
        )

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                repeat=3,
                run_id="run-pass",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert result.smoke_passed is True
        assert result.business is not None
        assert result.report_pdf is not None
        assert result.exit_code == 0
        assert len(fake_pytest.commands) == 2
        assert "e2e and smoke" in fake_pytest.commands[0]
        assert "e2e and not smoke" in fake_pytest.commands[1]
        repeat_index = fake_pytest.commands[1].index("--repeat") + 1
        assert fake_pytest.commands[1][repeat_index] == "3"

    def test_default_repeat_is_not_passed_to_pytest(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest(
            [_phase_payload(["通过"]), _phase_payload(["通过"])],
            [0, 0],
        )

        run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-default-repeat",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert all("--repeat" not in command for command in fake_pytest.commands)

    def test_manifest_paths_are_used_only_for_business_phase(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest(
            [_phase_payload(["通过"]), _phase_payload(["通过"])],
            [0, 0],
        )

        run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-manifest-selection",
                business_paths=(
                    Path("/repo/test_cases/test_one.py"),
                    Path("/repo/test_cases/test_two.py"),
                ),
                business_selection_source="stage2-manifest.json",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert "/repo/test_cases/test_one.py" not in fake_pytest.commands[0]
        assert "/repo/test_cases/test_one.py" in fake_pytest.commands[1]
        assert "/repo/test_cases/test_two.py" in fake_pytest.commands[1]
        payload = json.loads(
            (tmp_path / "run-manifest-selection" / "report.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["business_selection"]["path_count"] == 2
        assert payload["business_selection"]["source"] == "stage2-manifest.json"

    def test_failed_smoke_blocks_business_and_still_generates_report(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest([_phase_payload(["通过", "不通过"], exitstatus=1)], [1])

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-smoke-fail",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert result.smoke_passed is False
        assert result.business is None
        assert result.exit_code == 1
        assert len(fake_pytest.commands) == 1
        payload = json.loads(result.report_json.read_text(encoding="utf-8"))
        assert payload["business_executed"] is False
        assert payload["business"] is None

    def test_empty_smoke_suite_fails_closed(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest([_phase_payload([])], [0])

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-empty-smoke",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert result.smoke_passed is False
        assert result.business is None
        assert result.exit_code == 1

    def test_report_failure_preserves_json_and_uses_framework_exit_code(self, tmp_path: Path) -> None:
        fake_pytest = _FakePytest(
            [_phase_payload(["通过"]), _phase_payload(["无法判定"])],
            [0, 0],
        )

        def broken_pdf(_payload: object, _output: Path) -> None:
            raise RuntimeError("renderer unavailable")

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-report-fail",
            ),
            process_runner=fake_pytest,
            pdf_builder=broken_pdf,
        )

        assert result.exit_code == 2
        assert result.report_json.is_file()
        assert result.report_pdf is None
        assert (result.run_directory / "report-error.txt").is_file()

    def test_collection_error_fails_closed_even_when_reported_cases_pass(
        self, tmp_path: Path
    ) -> None:
        payload = _phase_payload(["通过"])
        payload["session"]["collection_errors"] = ["broken module"]  # type: ignore[index]
        fake_pytest = _FakePytest([payload], [0])

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-collection-error",
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert result.smoke_passed is False
        assert result.business is None

    def test_default_reportlab_builder_consumes_combined_workflow_payload(
        self, tmp_path: Path
    ) -> None:
        fake_pytest = _FakePytest(
            [_phase_payload(["通过"]), _phase_payload(["无法判定"])],
            [0, 0],
        )

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id="run-real-pdf",
            ),
            process_runner=fake_pytest,
        )

        assert result.exit_code == 0
        assert result.report_pdf is not None
        assert result.report_pdf.read_bytes().startswith(b"%PDF")
