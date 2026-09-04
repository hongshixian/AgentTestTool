"""Shared pytest fixtures for every Agent CLI product."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from agent_models import AgentModel, AgentModelFactory
from assertions.judge import JudgeConfig, OpenAICompatibleJudge
from configs import load_project_environment


load_project_environment()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--agent",
        action="store",
        default=os.environ.get("AGENT_PRODUCT", "codebuddy"),
        help="Agent CLI product passed to AgentModelFactory",
    )
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=os.environ.get("AGENT_E2E_ENABLED", "").lower() in {"1", "true", "yes"},
        help="Run tests that invoke a real Agent CLI and Judge API",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="需要通过 --run-e2e 显式启用真实 E2E 测试")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture
def agent_model(request: pytest.FixtureRequest, tmp_path) -> Iterator[AgentModel]:
    product = request.config.getoption("--agent")
    with AgentModelFactory.create(product, workspace=tmp_path) as model:
        yield model


@pytest.fixture
def judge_model() -> OpenAICompatibleJudge:
    try:
        config = JudgeConfig.from_environment()
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    return OpenAICompatibleJudge(config)
