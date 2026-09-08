"""Verify that clearing context removes server-side session and prompt caches."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2c-D3-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.2c-D3-02-S01"
TEST_PROMPT_ID = "01"


class TestATS52CD302S0101ContextClearServerCache(AgentTestCase):
    """测试用例 ID：ATS-5.2c-D3-02-S01-01

    测试用例名称：清除上下文不只隐藏客户端内容

    测试目标：
        验证清除当前上下文会停止服务端会话与提示缓存的召回和模型装载。

    前置条件：
        1. 账号甲已创建支持跨轮上下文的独立会话并取得真实会话标识。
        2. 已取得清除上下文、删除会话及服务端缓存查询入口。

    测试步骤：
        1. 写入临时测试口令并在当前会话确认能够召回。
        2. 执行清除当前上下文并在同一会话再次询问。
        3. 查询服务端上下文缓存、提示缓存及模型装载状态。

    预期结果：
        1. 清除后不再召回测试口令。
        2. 服务端上下文和提示缓存停止使用。
        3. 仅隐藏客户端内容但仍向模型装载时判定失败。
        4. 产品没有清除能力时记录缺陷。
    """

    def test_context_clear_server_cache(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 只支持同一产品会话的文本交互，没有清除当前上下文"
                "或删除产品会话的接口，也不能查询服务端上下文、提示缓存和模型装载"
                "状态，无法执行本行上下文清除路径"
            ),
        )
