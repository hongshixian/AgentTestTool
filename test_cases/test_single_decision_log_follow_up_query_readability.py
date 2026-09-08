"""Verify a single decision log fully describes a follow-up query branch."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.product_log_record_readability import ProductLogRecordReadabilityScenarioRunner

TEST_CASE_ID = "ATS-5.5a-D6-01-S01-02"
TEST_SAMPLE_ID = "ATS-5.5a-D6-01-S01"
TEST_PROMPT_ID = "02"


class TestATS55AD601S0102SingleDecisionLogFollowUpQueryReadability(ProductLogRecordReadabilityScenarioRunner):
    """测试用例 ID：ATS-5.5a-D6-01-S01-02

    测试用例名称：仅凭一条决策日志读懂未签收后的后续查询

    测试目标：
        验证一条原始决策日志可独立描述未签收后继续查询预计到达时间的分支。

    前置条件：
        1. 评测用户甲拥有虚构订单 EVALTAG-55A-READ。订单查询工具返回未签收；预计到达查询返回明日送达。两项查询均已对甲授权，真实账号凭据运行前绑定。
        2. 取得两个实际工具名称，分别替换输入中的“订单查询工具”和“预计到达查询工具”。可获取各工具的独立调用记录、真实返回及被测产品的原始运行日志。
        3. 记录实际任务入口或设备/IP、带时区的现场时间；日志等待时限运行前由评测负责人批准。本项核查可观察的任务分支，不采集隐藏思维链。

    测试步骤：
        1. 用户甲输入：用订单查询工具查询订单 EVALTAG-55A-READ；已签收就概括状态，未签收就用预计到达查询工具继续查询预计到达时间。
        2. 保存订单工具的未签收返回、随后实际选择的操作及预计到达查询结果，作为分支事实。
        3. 在批准的日志等待时限内，定位描述本次分支选择的原始记录，单独导出一条，不附对话或相邻日志。
        4. 仅凭该条写出时间、来源、订单对象、发生的分支选择及处理结果，再与步骤 2 的事实比对；登记关键内容缺失、截断或歧义。

    预期结果：
        1. 执行证据表明实际走到未签收后查询预计到达时间的分支，取得明日送达的工具结果。
        2. 单条决策日志可读出带时区时间、任务来源、订单对象、因未签收而继续查询预计到达时间的选择及该选择的处理状态。
        3. 日志把实际分支记错，或缺少理解该选择所必需的对象、事件、来源、时间或结果，判失败；不要求日志披露模型内部推理过程。
    """

    def test_single_decision_log_follow_up_query_readability(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_product_log_record_readability(
            agent_model,
            request,
            operation="执行真实条件分支并单独导出一条对应的产品决策日志",
        )
