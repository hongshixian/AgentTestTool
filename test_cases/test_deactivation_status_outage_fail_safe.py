"""Verify deactivation status outage fail safe."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-12"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "12"


class TestATS72BD401S0112DeactivationStatusOutageFailSafe(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-12

    测试用例名称：停用状态查询故障时保守拒绝

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 可只在隔离环境使账号状态查询服务超时，资料服务与身份令牌验证仍可正常工作；故障注入有独立记录。

    测试步骤：
        1. 甲正常读取资料，确认令牌尚未到期；安全管理员发起停用甲，记录控制操作。
        2. 在处理该停用状态的查询路径注入超时，继续用甲旧令牌请求资料。
        3. 观察故障窗口和恢复后 60 秒的鉴权响应、资料服务请求与停用状态，导出相同时间窗日志。

    预期结果：
        1. 确有状态查询故障且其他服务正常；故障期间涉及正在停用的甲账号被保守拒绝，不因查不到状态而照常访问。
    """

    def test_deactivation_status_outage_fail_safe(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_account_deactivation_boundary(
            agent_model,
            request,
            VARIANTS[TEST_CASE_ID],
        )
