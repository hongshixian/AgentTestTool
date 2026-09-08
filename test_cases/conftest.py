"""Shared pytest fixtures for every Agent CLI product."""

from __future__ import annotations

import os
import uuid
from argparse import ArgumentTypeError
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_models import AgentModel, AgentModelFactory
from assertions import (
    ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
    ASSESSMENT_REASON_PROPERTY,
    ASSESSMENT_STATUS_PROPERTY,
    AssessmentOutcomeSignal,
    AssessmentStatus,
)
from assertions.judge import JudgeConfig, OpenAICompatibleJudge
from configs import load_project_environment


load_project_environment()

_PHASE_REPORTS: pytest.StashKey[dict[str, dict[str, object]]] = pytest.StashKey()


def _apply_assessment_signal(
    report: pytest.TestReport,
    signal: AssessmentOutcomeSignal,
) -> None:
    """Encode one explicit assessment assertion without using pytest skip."""
    verdict = signal.verdict
    existing = dict(report.user_properties)
    if ASSESSMENT_STATUS_PROPERTY not in existing:
        report.user_properties.append((ASSESSMENT_STATUS_PROPERTY, verdict.status.value))
    if ASSESSMENT_REASON_PROPERTY not in existing:
        report.user_properties.append((ASSESSMENT_REASON_PROPERTY, verdict.reason))
    if ASSESSMENT_MISSING_EVIDENCE_PROPERTY not in existing:
        report.user_properties.append(
            (
                ASSESSMENT_MISSING_EVIDENCE_PROPERTY,
                "；".join(verdict.missing_evidence),
            )
        )
    report.outcome = "failed" if verdict.status is AssessmentStatus.FAIL else "passed"
    report.longrepr = (
        f"{verdict.status.value}：{verdict.reason}"
        if verdict.status is AssessmentStatus.FAIL
        else None
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Translate explicit four-state assertions and retain phase outcomes."""
    outcome = yield
    report = outcome.get_result()
    excinfo = getattr(call, "excinfo", None)
    signal = excinfo.value if excinfo is not None else None
    if isinstance(signal, AssessmentOutcomeSignal):
        _apply_assessment_signal(report, signal)
    report_properties = getattr(report, "user_properties", item.user_properties)
    phases = item.stash.setdefault(_PHASE_REPORTS, {})
    phases[report.when] = {
        "outcome": report.outcome,
        "assessment_status": dict(report_properties).get(
            ASSESSMENT_STATUS_PROPERTY
        ),
        "duration_seconds": report.duration,
    }


def pytest_report_teststatus(
    report: pytest.TestReport,
    config: pytest.Config,
) -> tuple[str, str, str] | None:
    """Render explicit assessment assertions using the workbook's four states."""
    properties = dict(report.user_properties)
    if report.when != "call":
        return None
    status_value = properties.get(ASSESSMENT_STATUS_PROPERTY)
    statuses = {
        AssessmentStatus.PASS.value: ("assessment_passed", ".", AssessmentStatus.PASS.value),
        AssessmentStatus.FAIL.value: ("assessment_failed", "F", AssessmentStatus.FAIL.value),
        AssessmentStatus.NOT_APPLICABLE.value: (
            "not_applicable",
            "N",
            AssessmentStatus.NOT_APPLICABLE.value,
        ),
        AssessmentStatus.INCONCLUSIVE.value: (
            "inconclusive",
            "I",
            AssessmentStatus.INCONCLUSIVE.value,
        ),
    }
    return statuses.get(status_value)


def _positive_repeat_count(value: str) -> int:
    try:
        repeat_count = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--repeat 必须是正整数") from error
    if repeat_count < 1:
        raise ArgumentTypeError("--repeat 必须是正整数")
    return repeat_count


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--evidence-dir", action="store", default="artifacts",
                     help="Parent directory for per-run redacted evidence (default: artifacts)")
    parser.addoption(
        "--agent",
        action="store",
        default=os.environ.get("AGENT_PRODUCT", "codebuddy"),
        help="Agent CLI product passed to AgentModelFactory",
    )
    parser.addoption(
        "--smoke",
        action="store_true",
        default=False,
        help="Run unit tests and only the minimal smoke subset of E2E cases",
    )
    parser.addoption(
        "--repeat",
        action="store",
        type=_positive_repeat_count,
        default=1,
        metavar="COUNT",
        help="Run each repeat-aware test case COUNT times (default: 1)",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "repeat_index" not in metafunc.fixturenames:
        return
    repeat_count = metafunc.config.getoption("--repeat")
    repeat_indices = range(1, repeat_count + 1)
    metafunc.parametrize(
        "repeat_index",
        repeat_indices,
        ids=[f"repeat-{index}" for index in repeat_indices],
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--smoke"):
        return
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if "e2e" in item.keywords and "smoke" not in item.keywords:
            deselected.append(item)
        else:
            selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)


@pytest.fixture
def agent_model(request: pytest.FixtureRequest, tmp_path) -> Iterator[AgentModel]:
    product = request.config.getoption("--agent")
    run_id = uuid.uuid4().hex
    evidence_directory = Path(request.config.getoption("--evidence-dir")).resolve() / run_id
    with AgentModelFactory.create(product, workspace=tmp_path,
                                  evidence_directory=evidence_directory, run_id=run_id) as model:
        request.node.user_properties.append(("evidence_directory", str(model.environment.evidence_directory)))
        model.environment.ledger.record("pytest", "case_started", {"node_id": request.node.nodeid})
        try:
            yield model
        finally:
            model.environment.ledger.save_artifact("pytest_outcome", {
                "node_id": request.node.nodeid,
                "phases": request.node.stash.get(_PHASE_REPORTS, {}),
                "scope": "setup/call reported before fixture cleanup; final teardown outcome is in pytest report",
            })


@pytest.fixture
def judge_model() -> OpenAICompatibleJudge | None:
    try:
        config = JudgeConfig.from_environment()
    except ValueError:
        return None
    return OpenAICompatibleJudge(config)
