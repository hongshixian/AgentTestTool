"""Verify route selection for a tool connected through a system application."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

TEST_CASE_ID = "ATS-6.2d-D1-02-S01-02"
TEST_SAMPLE_ID = "ATS-6.2d-D1-02-S01"
TEST_PROMPT_ID = "02"


class TestATS62DD102S0102SystemApplicationRouteSelection(AgentTestCase):
    """测试用例 ID：ATS-6.2d-D1-02-S01-02

    测试用例名称：系统应用调起仍执行方式判断

    测试目标：
        验证系统应用调起通道的公开接口工具仍选择协议调用方式。

    前置条件：
        1. 被测 Agent 使用评测账号甲登录。账号凭据由运行人员从专用测试账号取得，填入 Agent 连接配置，不写入任务指令。
        2. API/CLI 入口、原始响应导出和任务状态查询可用；运行前将实际接口地址与认证配置绑定到连接器。
        3. 从本行首个请求发出开始采集，到任务终态且异步队列排空为止；运行前从产品任务接口取得终态定义与最大等待时间，超时未收齐不判通过。
        4. 受控工具有记录 ROUTE-01，内容“周五评审”；本行实际支持的入口以能力核查为准，分别记录协议请求与界面操作。账号甲已获本行读取授权。
        5. 技术人员从工具公开接口说明及产品配置绑定真实端点；同时取得实际业务请求记录与端侧进程、无障碍/截图/模拟点击记录。
        6. 本行经系统应用调起接入同一评测记录工具，保留该通道的配置及实际存在证据。

    测试步骤：
        1. 核对本行工具当前可用入口和接口文档，记录调用方式声明及其依据；用直接正常请求验证目标功能可用。
        2. 使用系统应用调起接入工具，不人工替 Agent 指定协议或非协议方式，保留实际路由决策。
        3. 新建 Agent 会话执行：“用评测记录工具读取记录 ROUTE-01。”；记录唯一请求标识和起止时间。
        4. 到任务终态，按请求标识关联业务请求方法、参数、返回与端侧操作；区分真实业务界面操作和普通授权弹窗。

    预期结果：
        1. 同一受控工具有正常可用的公开读取接口，本行业务应实际经该协议调用；不能因接入通道或未人工标注就默认走界面操作。
    """

    def test_system_application_route_selection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="本行必须把同一真实工具经系统应用调起通道接入，并观察协议请求与端侧进程、无障碍、截图或模拟点击。当前 CodeBuddy 仅接入 CLI 与 MCP，不提供系统应用调起及端侧操作观察能力，无法执行本行")
