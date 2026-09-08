"""Verify that three-device sessions follow the declared concurrency policy."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1c-D4-01-S02-01"
TEST_SAMPLE_ID = "ATS-5.1c-D4-01-S02"
TEST_PROMPT_ID = "01"


class TestATS51CD401S0201MultiDeviceSessionPolicy(AgentTestCase):
    """测试用例 ID：ATS-5.1c-D4-01-S02-01

    测试用例名称：三设备并发会话遵守产品策略

    测试目标：
        验证账号甲在三台设备的并发会话符合声明策略，单点互踢时旧凭证在服务端失效。

    前置条件：
        1. 已在账号甲写入三条未完成待办并取得声明的并发策略。
        2. 已准备三台独立设备或隔离浏览器会话。
        3. 可以保存各会话的服务端凭证并查询安全日志。

    测试步骤：
        1. 在三台设备同时建立账号甲会话并请求上一条待办。
        2. 按声明策略核对保留和退出的会话。
        3. 声明单点互踢时，使用被踢会话原凭证直接重放待办请求。
        4. 保存会话状态、请求、响应和安全日志。

    预期结果：
        1. 允许并发时三个会话按声明保持有效。
        2. 单点登录时被踢会话的旧凭证在服务端失效。
        3. 前端页面跳转不能替代后端凭据失效证据。
    """

    def test_three_device_sessions_follow_declared_policy(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前框架没有三台独立设备或隔离浏览器会话控制能力，不能导出各会话"
                "服务端凭证或在被踢会话中指定旧凭证重放，也没有产品并发策略和安全日志"
                "观察接口；测试侧线程并发不能替代真实多设备会话"
            ),
        )
