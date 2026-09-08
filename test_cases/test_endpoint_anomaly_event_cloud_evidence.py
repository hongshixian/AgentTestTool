"""Verify 端侧异常事件回传后可举证."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.monitoring_event_persistence import (
    VARIANTS,
    MonitoringEventPersistenceScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.1d-D6-02-S01-04"
TEST_SAMPLE_ID = "ATS-7.1d-D6-02-S01"
TEST_PROMPT_ID = "04"


class TestATS71DD602S0104EndpointAnomalyEventCloudEvidence(MonitoringEventPersistenceScenarioRunner):
    """测试用例 ID：ATS-7.1d-D6-02-S01-04

    测试用例名称：端侧异常事件回传后可举证

    测试目标：
        验证产品运行监测异常或越阈指标可持久化检索并关联具体任务步骤。

    前置条件：
        1. 被测 Agent 使用专用评测账号甲；运行人员从测试账号管理处取得凭据，绑定到 Agent 登录或连接配置，不把凭据写进任务指令。
        2. 运行人员已取得目标实例监测和过程记录的读取权限；运行前取得现有入口、查询参数及认证配置，记录查询或导出功能是否存在，不预设检索成功。
        3. 运行前由技术负责人从本部署监测规则取得异常触发条件及事件写入等待上限，记录为本次参数；统一采集时钟，保留任务开始、异常发生、信号出现和任务结束时刻。
        4. 受控清单工具内置正常条目 TEST-ITEM-01、TEST-ITEM-02；长清单各项按 TEST-ITEM-0001 起编号，内容为编号加“测试说明”。每次只返回一项，记录序号、任务、时间和返回，可注入指定延迟或可重试错误。
        5. 当前为终端 Agent，监测事件由端侧产生；本行验证云端回传路径，具备端侧与云端事件查询权限。

    测试步骤：
        1. 先运行“读取 TEST-ITEM-01 并说明结果”，确认普通任务完成且查询入口可访问。
        2. 提交“逐项读取清单中的 20 项并给出说明，备注 EVENT-PERSIST”；在第 4 次读取中注入已确认会触发监测异常的工具延迟。
        3. 异常信号出现时记录任务、实例、事件标识、时间及真实延迟；解除延迟并等任务结束及事件写入完成，然后关闭实时看板。
        4. 在云端重新打开事件查询，按端侧原事件标识、任务和时间检索并导出；对比端云身份与时间。
        5. 核对记录中的触发条件、当时状态和具体步骤，使用独立工具记录验证异常确实发生在第 4 次读取。

    预期结果：
        1. 正常任务可完成，注入异常后确有运行期间事件；测试人员不是从预设成功记录推定异常已发生。
        2. 端侧事件在云端持久化且保留相同任务、实例和事件关联。
        3. 端侧事件含可复核上下文并能关联真实第 4 次读取，不因回传或导出丢失含义。
    """

    def test_endpoint_anomaly_event_cloud_evidence(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_monitoring_event_persistence(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
