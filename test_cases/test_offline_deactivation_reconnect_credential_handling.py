"""Verify 离线期间下发后重连的端侧凭证处理."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_credential_coverage import (
    VARIANTS,
    AccountDeactivationCredentialCoverageScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D1-02-S01-06"
TEST_SAMPLE_ID = "ATS-7.2b-D1-02-S01"
TEST_PROMPT_ID = "06"


class TestATS72BD102S0106OfflineDeactivationReconnectCredentialHandling(AccountDeactivationCredentialCoverageScenarioRunner):
    """测试用例 ID：ATS-7.2b-D1-02-S01-06

    测试用例名称：离线期间下发后重连的端侧凭证处理

    测试目标：
        验证本行账号或凭证类型完整纳入账号停用和凭证失效覆盖范围。

    前置条件：
        1. 评测人员具备只读查看当前部署配置、相应实现材料和现场运行证据的权限；记录版本与取得时间，不修改生产配置。
        2. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        3. 产品有终端账号及本地登录缓存；取得端侧登录态存储、重连/启动流程及离线授权有效期配置。

    测试步骤：
        1. 检查终端离线未收到停用指令时的投递留存和重连顺序，记录离线授权边界与过期策略。
        2. 核对端侧首次受保护操作前的账号校验和凭证清理位置，并与一次真实状态变更记录对照。

    预期结果：
        1. 重连或启动先更新停用状态并清理失效凭证，再决定任务能否执行；未收到远端新策略期间的行为按明确离线授权范围另审。
    """

    def test_offline_deactivation_reconnect_credential_handling(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_account_deactivation_credential_coverage(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
