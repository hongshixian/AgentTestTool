"""Verify the public contract for selecting and reporting mother/child suites."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_test_tool import cli
from agent_test_tool.reporting import CaseCategory, CaseResult, ReportData
from agent_test_tool.result_plugin import ResultCollector
from agent_test_tool.runner import WorkflowConfig, run_workflow
from test_cases.conftest import pytest_addoption as add_test_case_options
from test_cases.conftest import pytest_collection_modifyitems


def _phase_payload(case_id: str = "ATS-TEST-S01-01") -> dict[str, object]:
    return {
        "schema_version": 1,
        "session": {
            "exitstatus": 0,
            "collected": 1,
            "reported_cases": 1,
            "internal_errors": [],
            "collection_errors": [],
        },
        "cases": [
            {
                "nodeid": "test_cases/test_case.py::TestCase::test_case",
                "test_case_id": case_id,
                "name": "套件契约用例",
                "status": "通过",
                "reason": "代表路径执行成功",
                "missing_evidence": [],
                "duration_seconds": 0.1,
                "pytest_status": "passed",
                "phases": {},
            }
        ],
        "summary": {
            "通过": 1,
            "不通过": 0,
            "不适用": 0,
            "无法判定": 0,
            "total": 1,
        },
    }


class _FakePytest:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        output_index = command.index("--agent-result-json") + 1
        Path(command[output_index]).write_text(
            json.dumps(_phase_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def _fake_pdf(_payload: object, output: Path) -> None:
    output.write_bytes(b"%PDF-suite-contract")


def _item(
    *,
    case_id: str,
    constants: dict[str, object] | None = None,
    smoke: bool = False,
) -> SimpleNamespace:
    module_values = {"TEST_CASE_ID": case_id, **(constants or {})}

    class Example:
        """测试用例名称：套件元数据采集"""

    return SimpleNamespace(
        nodeid=f"test_cases/test_case.py::TestExample::test_case[{case_id}]",
        name="test_case",
        module=SimpleNamespace(**module_values),
        cls=Example,
        keywords={"e2e": True, **({"smoke": True} if smoke else {})},
    )


def _report(status: str = "通过") -> SimpleNamespace:
    return SimpleNamespace(
        when="call",
        outcome="failed" if status == "不通过" else "passed",
        duration=0.1,
        user_properties=[
            ("assessment_status", status),
            ("assessment_reason", "代表路径执行成功"),
        ],
    )


class _CollectionHook:
    def __init__(self) -> None:
        self.deselected: list[object] = []

    def pytest_deselected(self, *, items: list[object]) -> None:
        self.deselected.extend(items)


class _CollectionConfig:
    def __init__(self, suite: str) -> None:
        self.suite = suite
        self.hook = _CollectionHook()

    def getoption(self, option: str) -> object:
        return self.suite if option == "--case-suite" else False


class _CollectionItem:
    def __init__(self, case_id: str, *, e2e: bool = True) -> None:
        self.module = SimpleNamespace(TEST_CASE_ID=case_id)
        self.keywords = {"e2e": True} if e2e else {}
        self.markers: list[str] = []

    def add_marker(self, marker: str) -> None:
        self.markers.append(marker)


class _OptionParser:
    def __init__(self) -> None:
        self.options: dict[str, dict[str, object]] = {}

    def getgroup(self, _name: str) -> _OptionParser:
        return self

    def addoption(self, name: str, **kwargs: object) -> None:
        self.options[name] = kwargs


class TestSuiteCLIContract:
    def test_child_is_the_backward_compatible_default(self) -> None:
        args = cli.build_parser().parse_args([])

        assert args.suite == "child"

    @pytest.mark.parametrize("suite", ("mother", "child", "all"))
    def test_parser_accepts_each_supported_suite(self, suite: str) -> None:
        args = cli.build_parser().parse_args(["--suite", suite])

        assert args.suite == suite

    @pytest.mark.parametrize("suite", ("mother", "all"))
    def test_manifest_is_rejected_for_non_child_suites(
        self,
        tmp_path: Path,
        suite: str,
    ) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "cases": [
                        {
                            "script": (
                                "test_cases/"
                                "test_plaintext_rule_override_sample_01.py"
                            )
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(SystemExit) as raised:
            cli.main(
                [
                    "--suite",
                    suite,
                    "--business-manifest",
                    str(manifest),
                ]
            )

        assert "business-manifest" in str(raised.value)
        assert "child" in str(raised.value)


class TestSuiteRunnerContract:
    @pytest.mark.parametrize("suite", ("mother", "child", "all"))
    def test_suite_filter_is_applied_only_to_the_business_phase(
        self,
        tmp_path: Path,
        suite: str,
    ) -> None:
        fake_pytest = _FakePytest()

        result = run_workflow(
            WorkflowConfig(
                agent="codebuddy",
                output_parent=tmp_path,
                run_id=f"run-{suite}",
                suite=suite,
            ),
            process_runner=fake_pytest,
            pdf_builder=_fake_pdf,
        )

        assert result.smoke_passed is True
        assert len(fake_pytest.commands) == 2
        smoke_option_index = fake_pytest.commands[0].index("--case-suite") + 1
        assert fake_pytest.commands[0][smoke_option_index] == "all"
        option_index = fake_pytest.commands[1].index("--case-suite") + 1
        assert fake_pytest.commands[1][option_index] == suite
        report = json.loads(result.report_json.read_text(encoding="utf-8"))
        assert report["business_selection"]["suite"] == suite

    @pytest.mark.parametrize("suite", ("mother", "all"))
    def test_runner_rejects_manifest_paths_outside_child_suite(
        self,
        tmp_path: Path,
        suite: str,
    ) -> None:
        with pytest.raises(ValueError, match="child"):
            run_workflow(
                WorkflowConfig(
                    agent="codebuddy",
                    output_parent=tmp_path,
                    run_id=f"run-manifest-{suite}",
                    suite=suite,
                    business_paths=(Path("test_cases/test_example.py"),),
                ),
                process_runner=_FakePytest(),
                pdf_builder=_fake_pdf,
            )


class TestSuiteCollectionContract:
    def test_direct_pytest_defaults_to_child_suite(self) -> None:
        parser = _OptionParser()

        add_test_case_options(parser)  # type: ignore[arg-type]

        assert parser.options["--case-suite"]["default"] == "child"

    @pytest.mark.parametrize(
        ("suite", "expected_ids"),
        (
            ("mother", ["TC-6.1b-D5-01", "FRAMEWORK-OFFLINE"]),
            ("child", ["ATS-6.1b-D5-01-S01-01", "FRAMEWORK-OFFLINE"]),
            (
                "all",
                [
                    "TC-6.1b-D5-01",
                    "ATS-6.1b-D5-01-S01-01",
                    "FRAMEWORK-OFFLINE",
                ],
            ),
        ),
    )
    def test_collection_filters_only_e2e_business_levels(
        self,
        suite: str,
        expected_ids: list[str],
    ) -> None:
        mother = _CollectionItem("TC-6.1b-D5-01")
        child = _CollectionItem("ATS-6.1b-D5-01-S01-01")
        offline = _CollectionItem("FRAMEWORK-OFFLINE", e2e=False)
        items = [mother, child, offline]
        config = _CollectionConfig(suite)

        pytest_collection_modifyitems(config, items)  # type: ignore[arg-type]

        assert [item.module.TEST_CASE_ID for item in items] == expected_ids
        assert mother.markers == ["mother_case"]
        assert child.markers == ["child_case"]
        assert offline.markers == []

    @pytest.mark.parametrize("suite", ("mother", "child", "all"))
    def test_business_suite_never_deselects_smoke_cases(self, suite: str) -> None:
        smoke = _CollectionItem("ATS-0.0x-D0-01-S01-01")
        smoke.keywords["smoke"] = True
        items = [smoke]
        config = _CollectionConfig(suite)

        pytest_collection_modifyitems(config, items)  # type: ignore[arg-type]

        assert items == [smoke]
        assert config.hook.deselected == []
        assert smoke.markers == []


class TestSuiteResultMetadataContract:
    def test_mother_case_preserves_explicit_representative_path(
        self,
        tmp_path: Path,
    ) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-mother")
        item = _item(
            case_id="TC-6.1b-D5-01",
            constants={
                "TEST_CASE_LEVEL": "mother",
                "SOURCE_CASE_ID": "TC-6.1b-D5-01",
                "REPRESENTATIVE_CHILD_ID": "ATS-6.1b-D5-01-S01-01",
            },
        )

        collector.record_report(item, _report())
        case = collector.build_payload(exit_status=0)["cases"][0]

        assert case["case_level"] == "mother"
        assert case["source_case_id"] == "TC-6.1b-D5-01"
        assert case["representative_child_id"] == "ATS-6.1b-D5-01-S01-01"

    def test_existing_ats_case_derives_child_and_source_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-child")
        item = _item(case_id="ATS-6.1b-D5-01-S03-01")

        collector.record_report(item, _report())
        case = collector.build_payload(exit_status=0)["cases"][0]

        assert case["case_level"] == "child"
        assert case["source_case_id"] == "TC-6.1b-D5-01"
        assert case["representative_child_id"] == ""

    def test_json_statistics_keep_mother_and_child_results_separate(
        self,
        tmp_path: Path,
    ) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-all")
        mother = _item(case_id="TC-6.1b-D5-01")
        child = _item(case_id="ATS-6.1b-D5-01-S01-01")
        collector.record_report(mother, _report("通过"))
        collector.record_report(child, _report("不通过"))

        payload = collector.build_payload(exit_status=1)

        assert payload["summary_by_case_level"] == {
            "mother": {
                "通过": 1,
                "不通过": 0,
                "不适用": 0,
                "无法判定": 0,
                "total": 1,
            },
            "child": {
                "通过": 0,
                "不通过": 1,
                "不适用": 0,
                "无法判定": 0,
                "total": 1,
            },
        }

    def test_report_case_model_retains_suite_metadata(self) -> None:
        case = CaseResult.from_mapping(
            {
                "test_case_id": "TC-6.1b-D5-01",
                "name": "系统配置提取",
                "status": "通过",
                "reason": "未观察到明确失败事实",
                "case_level": "mother",
                "source_case_id": "TC-6.1b-D5-01",
                "representative_child_id": "ATS-6.1b-D5-01-S01-01",
            },
            default_category=CaseCategory.BUSINESS,
        )

        assert case.case_level == "mother"
        assert case.source_case_id == "TC-6.1b-D5-01"
        assert case.representative_child_id == "ATS-6.1b-D5-01-S01-01"

    def test_combined_report_uses_the_business_suite_as_run_metadata(self) -> None:
        smoke_payload = {
            "run_id": "run-suite-metadata",
            "case_suite": "all",
            "session": {},
            "cases": [],
        }
        business_payload = {
            "run_id": "run-suite-metadata",
            "case_suite": "mother",
            "session": {},
            "cases": [],
        }

        report = ReportData.from_pytest_payloads(smoke_payload, business_payload)

        assert report.metadata.case_suite == "mother"

    def test_legacy_payloads_are_grouped_by_case_id_prefix(self) -> None:
        report = ReportData.from_mapping(
            {
                "cases": [
                    {
                        "test_case_id": "TC-6.1b-D5-01",
                        "status": "通过",
                    },
                    {
                        "test_case_id": "ATS-6.1b-D5-01-S01-01",
                        "status": "不通过",
                    },
                ]
            }
        )

        assert [case.case_id for case in report.mother_results] == [
            "TC-6.1b-D5-01"
        ]
        assert [case.case_id for case in report.child_results] == [
            "ATS-6.1b-D5-01-S01-01"
        ]
