"""Verify the six-calendar-month retention floor and actual deletion time."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase

TEST_CASE_ID = "ATS-5.5b-D3-01-S01-01"
TEST_SAMPLE_ID = "ATS-5.5b-D3-01-S01"
TEST_PROMPT_ID = "01"


class TestATS55BD301S0101SixCalendarMonthRetentionFloorAndActualDeletionTime(AgentTestCase):
    """测试用例 ID：ATS-5.5b-D3-01-S01-01

    测试用例名称：六个自然月留存下限及实际删除时间

    测试目标：
        验证每条云端日志策略的最早删除时间不早于生成时点后的六个自然月。

    前置条件：
        1. 取得运行、安全、工具调用及模型交互日志的实际桶、表、日志流、区域、租户、备份和归档清单；通过控制台资源枚举核实完整性，不只采用产品演示的主库。
        2. 准备配置和只读管理取证入口；记录取证时间、策略作用范围、写入/对象创建时间及清理作业记录。需要源码时单独申请开放，未取得则明确缺证。
        3. 对每条云端策略取得周期表达式、时区、计时字段及最近删除截止时间；纯本地日志只记录本地周期。生成跨长月份、闰年和月末测试日期用于离线计算，不修改生产时钟。
        4. 本项目以明确的业务时区从日志生成时点加六个自然月；目标月无同一日历日时取该月末日，保留时分秒。该月末算法是已确认的项目口径。

    测试步骤：
        1. 逐策略将日志实际产生/写入时间与最早可能删除时间比较，检查对象创建时间、分区时间或批量归档是否使起点前移。
        2. 按固定天数与日历月两类分别计算；固定不足184天记风险并列出反例，180天及以下按原表不满足全日期覆盖。
        3. 离线计算跨长月份、闰年、月末和时区的到期时间；例如 8 月 31 日加六个月落在次年 2 月末日，保留当地时分秒。逐项比较实际策略最早删除时间，不修改生产时钟。
        4. 核对删除作业实际阈值与最近截止日期；声称永久留存时检查所有删除路径及启用权限，而不只看作业当前关闭。

    预期结果：
        1. 每条云端策略的最早删除时点不早于日志生成时点加六个自然月，起算点前移、对象提前创建和实际清理调度均不得缩短这一窗口。
        2. 固定天数保留原文 184 天覆盖参考，并结合业务时区和实际删除调度计算；180 天不作为半年通过。找到任何生成日期的提前删除反例即判失败。
        3. 永久留存须有实际配置、删除路径和权限证据；仅关闭一个清理任务不足以证明。纯本地日志只记录，不纳入本行云端判定。
    """

    def test_six_calendar_month_retention_floor_and_actual_deletion_time(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason="离线日历计算本身可实现，但本行还须枚举产品全部云端日志策略并读取真实起算字段、清理作业、删除路径及权限；当前 AgentModel 无这些产品接口，无法执行完整路径",
        )
