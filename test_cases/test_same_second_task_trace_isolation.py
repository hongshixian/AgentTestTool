"""Verify same-second task traces remain isolated."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.concurrent_product_task_trace import ConcurrentProductTaskTraceScenarioRunner

TEST_CASE_ID = "ATS-5.5e-D2-02-S02-01"
TEST_SAMPLE_ID = "ATS-5.5e-D2-02-S02"
TEST_PROMPT_ID = "01"


class TestATS55ED202S0201SameSecondTaskTraceIsolation(ConcurrentProductTaskTraceScenarioRunner):
    """测试用例 ID：ATS-5.5e-D2-02-S02-01

    测试用例名称：任务甲与任务乙同秒归集不串扰

    测试目标：
        验证同秒发生的两个任务调用仍按真实任务标识正确归集。

    前置条件：
        1. 准备独立评测账号甲、只访问虚构订单的查询工具及其独立调用记录；运行前从注册表取得工具实际调用名并替换本行中文工具名。
        2. 取得运行日志、安全日志的检索/导出入口和字段说明，记录时区、时钟偏差及现场测试起止时间。日志落地等待时限运行前由评测负责人批准，不把当前查不到直接当永久丢失。
        3. 准备任务标识查询/导出入口、运行与安全日志字段字典，以及独立工具端的请求、参数、返回及时间记录；明确产品“任务”起止边界与请求、会话的区别。
        4. 甲拥有虚构订单 EVALTAG-55E-02A 和 EVALTAG-55E-02B，可建立两个独立任务；准备工具端同步屏障、亚秒时间及独立请求 ID 的采集入口。

    测试步骤：
        1. 账号甲分别建立任务甲和任务乙，输入“查询订单 EVALTAG-55E-02A”和“查询订单 EVALTAG-55E-02B”。在工具端同时释放等待的两次调用，保存实际时间以核实重叠及至少一对调用处于同一秒。
        2. 结束后分别按两个任务 ID 重建，逐调用核对订单号、返回及请求 ID，检查交错和同秒事实。

    预期结果：
        1. 实际重叠且同秒的两次调用，分别只归对应的任务甲和任务乙，订单、参数、返回和请求 ID 与工具端证据一致。
        2. 调用错归、漏归或同时归入两链，判失败；提交时间相同但实际调用未重叠或不同秒，只记该边界未触发。
    """

    def test_same_second_task_trace_isolation(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_concurrent_product_task_trace(
            agent_model, request, operation="让任务甲乙工具调用真实重叠且同秒并按产品任务 ID 重建两链"
        )
