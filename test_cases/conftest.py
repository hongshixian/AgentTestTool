"""Shared pytest fixtures for every Agent CLI product."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from agent_models import AgentModel, AgentModelFactory
from assertions.judge import JudgeConfig, OpenAICompatibleJudge
from configs import load_project_environment
from test_cases.security import SecurityIdentitySettings


load_project_environment()


def pytest_addoption(parser: pytest.Parser) -> None:
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
    with AgentModelFactory.create(product, workspace=tmp_path) as model:
        yield model


@pytest.fixture
def judge_model() -> OpenAICompatibleJudge:
    try:
        config = JudgeConfig.from_environment()
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    return OpenAICompatibleJudge(config)


@pytest.fixture
def security_identities() -> SecurityIdentitySettings:
    try:
        return SecurityIdentitySettings.from_environment()
    except ValueError as error:
        pytest.skip(str(error))


@pytest.fixture
def destroyed_instance_id() -> str:
    value = os.environ.get("AGENT_TEST_DESTROYED_INSTANCE_ID", "").strip()
    if not value:
        pytest.skip("缺少显式安全测试配置：AGENT_TEST_DESTROYED_INSTANCE_ID")
    return value


@pytest.fixture
def isolated_test_device() -> str:
    value = os.environ.get("AGENT_TEST_DEVICE", "").strip()
    if not value:
        pytest.skip("缺少显式安全测试配置：AGENT_TEST_DEVICE")
    return value
