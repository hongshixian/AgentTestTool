"""Verify structured pytest result aggregation and atomic serialization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_test_tool.result_plugin import ResultCollector, _atomic_write_json


pytest_plugins = ("pytester",)


def _item(
    *,
    nodeid: str = "test_cases/test_example.py::TestExample::test_result",
    case_id: str = "ATS-1.1a-D1-01-S01-01",
    e2e: bool = True,
) -> SimpleNamespace:
    class Example:
        """测试用例 ID：ATS-1.1a-D1-01-S01-01

        测试用例名称：结构化结果采集
        """

    return SimpleNamespace(
        nodeid=nodeid,
        name="test_result",
        module=SimpleNamespace(TEST_CASE_ID=case_id),
        cls=Example,
        keywords={"e2e": True} if e2e else {},
    )


def _report(
    when: str,
    outcome: str,
    *,
    duration: float = 0.1,
    properties: tuple[tuple[str, object], ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        when=when,
        outcome=outcome,
        duration=duration,
        user_properties=list(properties),
    )


class TestResultCollector:
    """测试用例 ID：FRAMEWORK-RESULT-COLLECTOR

    测试用例名称：pytest 结构化结果聚合

    测试目标：
        1. 验证 pytest 阶段结果可聚合为稳定的四态记录。

    前置条件：
        1. 创建离线 pytest Item 和 Report 替身。

    测试步骤：
        1. 向结果采集器写入各阶段结果。
        2. 生成会话级 JSON 数据。

    预期结果：
        1. 测评状态、元数据、耗时和错误信息均被保留。
    """

    def test_aggregates_explicit_four_state_result(self, tmp_path: Path) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-001")
        item = _item()
        collector.collected_count = 1
        collector.record_report(item, _report("setup", "passed", duration=0.2))
        collector.record_report(
            item,
            _report(
                "call",
                "passed",
                duration=0.3,
                properties=(
                    ("assessment_status", "无法判定"),
                    ("assessment_reason", "缺少产品安全日志"),
                    ("assessment_missing_evidence", "安全日志；授权事件"),
                ),
            ),
        )
        collector.record_report(item, _report("teardown", "passed", duration=0.1))

        payload = collector.build_payload(exit_status=0, finished_at="2026-09-09T00:00:00+00:00")
        case = payload["cases"][0]

        assert case == {
            "nodeid": item.nodeid,
            "test_case_id": "ATS-1.1a-D1-01-S01-01",
            "name": "结构化结果采集",
            "case_level": "child",
            "source_case_id": "TC-1.1a-D1-01",
            "representative_child_id": "",
            "status": "无法判定",
            "reason": "缺少产品安全日志",
            "missing_evidence": ["安全日志", "授权事件"],
            "duration_seconds": 0.6,
            "pytest_status": "passed",
            "phases": case["phases"],
        }
        assert payload["summary"] == {
            "通过": 0,
            "不通过": 0,
            "不适用": 0,
            "无法判定": 1,
            "total": 1,
        }

    @pytest.mark.parametrize("failure_phase", ["setup", "call", "teardown"])
    def test_any_phase_failure_overrides_an_explicit_pass(
        self,
        tmp_path: Path,
        failure_phase: str,
    ) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-002")
        item = _item()
        collector.record_report(
            item,
            _report(
                "call",
                "passed",
                properties=(
                    ("assessment_status", "通过"),
                    ("assessment_reason", "功能符合预期"),
                ),
            ),
        )
        collector.record_report(
            item,
            _report(
                failure_phase,
                "failed",
                properties=(("assessment_reason", f"{failure_phase} 基础设施失败"),),
            ),
        )

        case = collector.build_payload(exit_status=1)["cases"][0]

        assert case["status"] == "不通过"
        assert case["reason"] == f"{failure_phase} 基础设施失败"
        assert case["pytest_status"] == ("failed" if failure_phase == "call" else "error")

    def test_zero_collection_and_internal_error_keep_session_metadata(
        self, tmp_path: Path
    ) -> None:
        collector = ResultCollector(tmp_path / "result.json", run_id="run-empty")
        collector.internal_errors.append("plugin crashed")
        collector.collection_errors.append("module import failed")

        payload = collector.build_payload(exit_status=int(pytest.ExitCode.INTERNAL_ERROR))

        assert payload["cases"] == []
        assert payload["summary"]["total"] == 0
        assert payload["session"]["pytest_status"] == "internal_error"
        assert payload["session"]["collected"] == 0
        assert payload["session"]["internal_errors"] == ["plugin crashed"]
        assert payload["session"]["collection_errors"] == ["module import failed"]

    def test_atomic_writer_replaces_existing_json(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "result.json"
        target.parent.mkdir()
        target.write_text('{"stale": true}', encoding="utf-8")

        _atomic_write_json(target, {"status": "通过"})

        assert json.loads(target.read_text(encoding="utf-8")) == {"status": "通过"}
        assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_plugin_loads_in_pytest_subprocess_and_writes_results(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(part for part in (str(repository_root), current_pythonpath) if part),
    )
    pytester.makeini(
        """
        [pytest]
        markers =
            e2e: public Agent E2E case
        """
    )
    pytester.makepyfile(
        """
        import pytest

        TEST_CASE_ID = "ATS-9.9a-D1-01-S01-01"

        @pytest.mark.e2e
        class TestResult:
            '''测试用例 ID：ATS-9.9a-D1-01-S01-01

            测试用例名称：子进程结果采集
            '''

            def test_inconclusive(self, record_property):
                record_property("assessment_status", "无法判定")
                record_property("assessment_reason", "缺少运行日志")
                record_property("assessment_missing_evidence", "运行日志")
    """
    )
    pytester.makepyfile(
        test_setup_error="""
        import pytest

        TEST_CASE_ID = "ATS-9.9a-D1-01-S01-02"
        pytestmark = pytest.mark.e2e

        @pytest.fixture
        def unavailable_cli():
            raise RuntimeError("CLI unavailable")

        class TestSetupFailure:
            '''测试用例 ID：ATS-9.9a-D1-01-S01-02

            测试用例名称：前置条件异常映射
            '''

            def test_setup_failure(self, unavailable_cli):
                raise AssertionError("unreachable")
        """
    )
    result_path = pytester.path / "result.json"

    result = pytester.runpytest_subprocess(
        "-p",
        "agent_test_tool.result_plugin",
        f"--agent-result-json={result_path}",
        "-q",
    )

    result.assert_outcomes(passed=1, errors=1)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["session"]["collected"] == 2
    cases = {case["test_case_id"]: case for case in payload["cases"]}
    assert cases["ATS-9.9a-D1-01-S01-01"]["status"] == "无法判定"
    assert cases["ATS-9.9a-D1-01-S01-01"]["name"] == "子进程结果采集"
    assert cases["ATS-9.9a-D1-01-S01-02"]["status"] == "不通过"
    assert cases["ATS-9.9a-D1-01-S01-02"]["pytest_status"] == "error"
    assert "setup" in cases["ATS-9.9a-D1-01-S01-02"]["reason"]


def test_plugin_excludes_marker_deselected_cases_from_json(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(part for part in (str(repository_root), current_pythonpath) if part),
    )
    pytester.makeini(
        """
        [pytest]
        markers =
            smoke: smoke gate case
        """
    )
    pytester.makepyfile(
        """
        import pytest

        TEST_CASE_ID = "ATS-SMOKE-SELECTION"

        @pytest.mark.smoke
        def test_smoke(record_property):
            record_property("assessment_status", "通过")
            record_property("assessment_reason", "冒烟检查成功")

        def test_business():
            raise AssertionError("must be deselected")
        """
    )
    result_path = pytester.path / "smoke-result.json"

    result = pytester.runpytest_subprocess(
        "-p",
        "agent_test_tool.result_plugin",
        f"--agent-result-json={result_path}",
        "-m",
        "smoke",
        "-q",
    )

    result.assert_outcomes(passed=1, deselected=1)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["session"]["collected"] == 1
    assert payload["session"]["reported_cases"] == 1
    assert [case["nodeid"] for case in payload["cases"]] == ["test_plugin_excludes_marker_deselected_cases_from_json.py::test_smoke"]
