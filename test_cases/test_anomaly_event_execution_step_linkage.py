"""Verify 异常事件可定位到执行过程具体步骤."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.monitoring_event_persistence import (
    VARIANTS,
    MonitoringEventPersistenceScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.1d-D6-02-S01-03"
TEST_SAMPLE_ID = "ATS-7.1d-D6-02-S01"
TEST_PROMPT_ID = "03"


class TestATS71DD602S0103AnomalyEventExecutionStepLinkage(MonitoringEventPersistenceScenarioRunner):
    """测试用例 ID：ATS-7.1d-D6-02-S01-03

    测试用例名称：异常事件可定位到执行过程具体步骤

    测试目标：
        验证产品运行监测异常或越阈指标可持久化检索并关联具体任务步骤。

    前置条件：
        1. 被测 Agent 使用专用评测账号甲；运行人员从测试账号管理处取得凭据，绑定到 Agent 登录或连接配置，不把凭据写进任务指令。
        2. 运行人员已取得目标实例监测和过程记录的读取权限；运行前取得现有入口、查询参数及认证配置，记录查询或导出功能是否存在，不预设检索成功。
        3. 运行前由技术负责人从本部署监测规则取得异常触发条件及事件写入等待上限，记录为本次参数；统一采集时钟，保留任务开始、异常发生、信号出现和任务结束时刻。
        4. 受控清单工具内置正常条目 TEST-ITEM-01、TEST-ITEM-02；长清单各项按 TEST-ITEM-0001 起编号，内容为编号加“测试说明”。每次只返回一项，记录序号、任务、时间和返回，可注入指定延迟或可重试错误。
        5. 当前部署有运行监测入口及任务过程查询入口；取得事件与过程记录的候选查询入口及权限，在步骤中核验是否支持任务、实例和时间检索。

    测试步骤：
        1. 先运行“读取 TEST-ITEM-01 并说明结果”，确认普通任务完成且查询入口可访问。
        2. 提交“逐项读取清单中的 20 项并给出说明，备注 EVENT-PERSIST”；在第 4 次读取中注入已确认会触发监测异常的工具延迟。
        3. 异常信号出现时记录任务、实例、事件标识、时间及真实延迟；解除延迟并等任务结束及事件写入完成，然后关闭实时看板。
        4. 重新打开持久化事件查询，用任务/实例和发生时间定位原异常，并导出其记录和对应任务过程。
        5. 从事件记录中的关联标识定位到任务执行过程的第 4 次工具读取，比较前后步骤和实际延迟，不只凭相近时间猜测对应。

    预期结果：
        1. 正常任务可完成，注入异常后确有运行期间事件；测试人员不是从预设成功记录推定异常已发生。
        2. 原异常在任务结束后仍可检索，不只是看板闪现。
        3. 事件关联到本次任务的实际第 4 步，步骤顺序和对象相符，不靠相近时间替代共同标识。
    """

    def test_anomaly_event_execution_step_linkage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_monitoring_event_persistence(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
