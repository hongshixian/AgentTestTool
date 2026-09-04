"""Shared pytest fixtures for every Agent CLI product."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from agent_models import AgentModel, AgentModelFactory
from assertions.judge import JudgeConfig, OpenAICompatibleJudge


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--agent",
        action="store",
        default=os.environ.get("AGENT_PRODUCT", "codebuddy"),
        help="Agent CLI product passed to AgentModelFactory",
    )


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
