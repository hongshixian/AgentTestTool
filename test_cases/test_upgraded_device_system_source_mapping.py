"""Verify source mapping after upgrading the evaluation device system."""

import pytest
from agent_models import AgentModel
from test_cases.scenarios.attribution_continuity_boundaries import VARIANTS, AttributionContinuityBoundaryScenarioRunner

TEST_CASE_ID = "ATS-6.1c-D4-01-S01-02"
TEST_SAMPLE_ID = "ATS-6.1c-D4-01-S01"
TEST_PROMPT_ID = "02"


class TestATS61CD401S0102UpgradedDeviceSystemSourceMapping(AttributionContinuityBoundaryScenarioRunner):
    """测试用例 ID：ATS-6.1c-D4-01-S01-02

    测试用例名称：升级演练设备系统后的同源映射

    测试目标：
        验证演练设备系统升级后同一来源的前后输入仍可关联。

    前置条件：
        1. 准备被测实例和真实输入归属查询、原始日志导出入口；记录时区、字段映射和日志落地时限，运行前由负责人批准。真实凭据及各入口地址从部署登记取得后绑定。
        2. 准备甲的真实登录身份和会议任务入口；所有输入的归属与系统鉴别记录可对照。
        3. 仅用于可恢复演练终端。备份本地归属和服务端记录；绑定可核验的同一设备及甲的同一已登录账号，准备对应变更包、版本和恢复办法。匿名新安装不强制关联旧身份。

    测试步骤：
        1. 甲在原设备输入：将“小林交纪要；小周核预算；小陈回客户”整理成三条待办，备注 EVALTAG-61C-D4-04-BEFORE。保存原设备及账号核验事实、输入记录和旧归属。
        2. 在该演练设备上升级演练设备系统；记录实际版本及设备标识变化，重新登录甲的同一账号。
        3. 甲输入相同三项会议任务，备注 EVALTAG-61C-D4-04-AFTER；导出变更前后本地归属和服务端映射，按两个标记核对同源关联。

    预期结果：
        1. 升级演练设备系统后，已核验同一来源的前后输入可凭持久映射关联，账号、设备和变更记录支持该关联。
        2. 新旧记录成为互不相关来源且无可出示映射为失败；口头认定同一设备不足。纯网络无此边界单项不涉及，不据此豁免其他归属边界。
    """

    def test_upgraded_device_system_source_mapping(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.run_attribution_continuity_boundary(agent_model, request, VARIANTS[TEST_CASE_ID])
