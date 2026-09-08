"""Shared pytest fixtures for every Agent CLI product."""

from __future__ import annotations

import os
import uuid
from argparse import ArgumentTypeError
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_models import AgentModel, AgentModelFactory
from assertions import ASSESSMENT_STATUS_PROPERTY, AssessmentStatus
from assertions.judge import JudgeConfig, OpenAICompatibleJudge
from configs import load_project_environment


load_project_environment()

_PHASE_REPORTS: pytest.StashKey[dict[str, dict[str, object]]] = pytest.StashKey()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Retain pytest phase outcomes for the run-local evidence manifest."""
    outcome = yield
    report = outcome.get_result()
    phases = item.stash.setdefault(_PHASE_REPORTS, {})
    phases[report.when] = {"outcome": report.outcome, "duration_seconds": report.duration}


def pytest_report_teststatus(
    report: pytest.TestReport,
    config: pytest.Config,
) -> tuple[str, str, str] | None:
    """Render evidence-limited cases using the workbook's ‘无法判定’ status."""
    properties = dict(report.user_properties)
    if (
        report.when == "call"
        and report.skipped
        and properties.get(ASSESSMENT_STATUS_PROPERTY)
        == AssessmentStatus.INCONCLUSIVE.value
    ):
        return "inconclusive", "I", AssessmentStatus.INCONCLUSIVE.value
    return None


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
    skip_non_smoke_e2e = pytest.mark.skip(reason="smoke 模式仅执行最小 E2E 用例集")
    for item in items:
        if "e2e" in item.keywords and "smoke" not in item.keywords:
            item.add_marker(skip_non_smoke_e2e)


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
def judge_model() -> OpenAICompatibleJudge:
    try:
        config = JudgeConfig.from_environment()
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    return OpenAICompatibleJudge(config)
