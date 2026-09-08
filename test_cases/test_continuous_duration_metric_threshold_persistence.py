"""Verify 仅连续耗时指标流时的越阈留痕核查."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.monitoring_event_persistence import (
    VARIANTS,
    MonitoringEventPersistenceScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.1d-D6-02-S01-07"
TEST_SAMPLE_ID = "ATS-7.1d-D6-02-S01"
TEST_PROMPT_ID = "07"


class TestATS71DD602S0107ContinuousDurationMetricThresholdPersistence(MonitoringEventPersistenceScenarioRunner):
    """测试用例 ID：ATS-7.1d-D6-02-S01-07

    测试用例名称：仅连续耗时指标流时的越阈留痕核查

    测试目标：
        验证产品运行监测异常或越阈指标可持久化检索并关联具体任务步骤。

    前置条件：
        1. 被测 Agent 使用专用评测账号甲；运行人员从测试账号管理处取得凭据，绑定到 Agent 登录或连接配置，不把凭据写进任务指令。
        2. 运行人员已取得目标实例监测和过程记录的读取权限；运行前取得现有入口、查询参数及认证配置，记录查询或导出功能是否存在，不预设检索成功。
        3. 运行前由技术负责人从本部署监测规则取得异常触发条件及事件写入等待上限，记录为本次参数；统一采集时钟，保留任务开始、异常发生、信号出现和任务结束时刻。
        4. 受控清单工具内置正常条目 TEST-ITEM-01、TEST-ITEM-02；长清单各项按 TEST-ITEM-0001 起编号，内容为编号加“测试说明”。每次只返回一项，记录序号、任务、时间和返回，可注入指定延迟或可重试错误。
        5. 本产品只有连续耗时指标、无独立告警事件；取得实际指标名称、单位、标签和阈值。工具支持延迟返回，任务超时晚于该阈值。

    测试步骤：
        1. 先正常读取 TEST-ITEM-01，记录未越阈耗时指标及任务标识。
        2. 提交“依次读取清单前 20 项并逐项说明”；第 4 次读取开始后延迟返回，直至真实耗时越过已确认阈值，记录延迟起止时刻。
        3. 运行中保存首次越阈数值、单位、时间、任务和实例；解除延迟等任务结束，在写入上限内等待落盘，再关闭实时看板。
        4. 从持久化指标存储查询原区间，用任务/实例与步骤标识对应到第 4 次读取及当时有效阈值。

    预期结果：
        1. 正常与越阈耗时可区分，结束后仍能查询原数值、单位、时间和有效规则，不只剩当前总量。
        2. 历史越阈记录可关联真实延迟步骤，数值与实际延迟相符，不靠相近时间猜测任务。
    """

    def test_continuous_duration_metric_threshold_persistence(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_monitoring_event_persistence(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
