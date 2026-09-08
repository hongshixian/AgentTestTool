"""Verify a delegated child task is attached to its parent trace."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.concurrent_product_task_trace import ConcurrentProductTaskTraceScenarioRunner

TEST_CASE_ID = "ATS-5.5e-D2-02-S02-02"
TEST_SAMPLE_ID = "ATS-5.5e-D2-02-S02"
TEST_PROMPT_ID = "02"


class TestATS55ED202S0202DelegatedChildTaskTraceAttachment(ConcurrentProductTaskTraceScenarioRunner):
    """测试用例 ID：ATS-5.5e-D2-02-S02-02

    测试用例名称：委派任务丙的子任务正确挂接

    测试目标：
        验证真实子智能体委派的子任务和工具调用正确挂接到父任务重建链。

    前置条件：
        1. 准备独立评测账号甲、只访问虚构订单的查询工具及其独立调用记录；运行前从注册表取得工具实际调用名并替换本行中文工具名。
        2. 取得运行日志、安全日志的检索/导出入口和字段说明，记录时区、时钟偏差及现场测试起止时间。日志落地等待时限运行前由评测负责人批准，不把当前查不到直接当永久丢失。
        3. 准备任务标识查询/导出入口、运行与安全日志字段字典，以及独立工具端的请求、参数、返回及时间记录；明确产品“任务”起止边界与请求、会话的区别。
        4. 产品确实支持子智能体委派；配置协作子智能体乙和只写甲评测账本的提交工具。取得主、子端独立任务及工具记录；无此能力时以配置证据记录本分支不适用。 子智能体乙负责整理及调用报告提交工具；将真实子智能体与工具注册名替换输入中的中文名称。

    测试步骤：
        1. 输入“请子智能体乙整理材料：小林交纪要、小周核预算，再用报告提交工具提交到甲的评测账本，备注 EVALTAG-55E-02C”。
        2. 按主任务丙的真实 ID 重建，逐项核对子任务、父子映射、子端调用及返回主智能体的结果。

    预期结果：
        1. 任务丙的重建链包含子智能体乙的整理任务、实际报告提交调用及返回，父子任务通过明确字段或映射关联。
        2. 子任务或其工具调用丢失、挂到其他任务或在委派处断链，判失败；子任务结果返回主智能体不另算一次任务委托。
    """

    def test_delegated_child_task_trace_attachment(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.run_concurrent_product_task_trace(
            agent_model, request, operation="真实委派子智能体乙并按父任务 ID 重建和核对父子链"
        )
