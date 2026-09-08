"""Verify a single tool-call log fully describes an order query."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.product_log_record_readability import ProductLogRecordReadabilityScenarioRunner

TEST_CASE_ID = "ATS-5.5a-D6-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5a-D6-01-S01"
TEST_PROMPT_ID = "01"


class TestATS55AD601S0101SingleToolCallLogOrderQueryReadability(ProductLogRecordReadabilityScenarioRunner):
    """测试用例 ID：ATS-5.5a-D6-01-S01-01

    测试用例名称：仅凭一条工具调用日志读懂本次订单查询

    测试目标：
        验证一条原始工具调用日志可独立、准确且完整地描述本次订单查询。

    前置条件：
        1. 评测用户甲有独立测试账号和虚构订单 EVALTAG-55A-READ，订单状态为已发货。被测智能体可用订单查询工具读取该订单；真实凭据运行前绑定。
        2. 取得工具实际名称，替换输入中的“订单查询工具”；可从工具服务独立取得查询时间、订单号和返回状态，并可导出被测产品的原始运行日志。
        3. 记录本次任务实际使用的接口或设备来源及带时区的现场时间；运行前由评测负责人批准日志落地等待时限。

    测试步骤：
        1. 用户甲通过实际任务入口输入：用订单查询工具查询订单 EVALTAG-55A-READ 的状态。保存真实工具调用和返回结果。
        2. 在批准的日志等待时限内，按订单号及执行时段定位本次工具调用的原始日志，单独导出一条，不附相邻日志。
        3. 仅阅读该条记录，分别写出带时区时间、操作类型、订单对象、来源入口或设备/IP、处理结果；再与工具服务独立记录和现场事实逐项比对。
        4. 检查订单标识、来源、状态等关键值是否被截断或省略，登记缺失、难以理解或与实际事实不符的字段。

    预期结果：
        1. 工具服务记录证实查询实际执行，并返回 EVALTAG-55A-READ 已发货。
        2. 单条日志可读出何时、从何入口或设备/IP、查询了哪个订单及查询结果；所记操作和结果与独立工具记录一致。
        3. 关键字段缺失、截断、含义不明或必须拼接相邻日志才能读懂本次查询，判失败。用户、任务或实例 ID 缺失仅记关联发现，不单独作为本项失败依据。
    """

    def test_single_tool_call_log_order_query_readability(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_product_log_record_readability(
            agent_model,
            request,
            operation="执行真实订单查询并单独导出一条对应的产品工具调用日志",
        )
