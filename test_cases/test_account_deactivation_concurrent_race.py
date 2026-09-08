"""Verify account deactivation concurrent race."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-01"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "01"


class TestATS72BD401S0101AccountDeactivationConcurrentRace(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-01

    测试用例名称：并发竞态下的账号停用

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 本行固定选择一个真实网关，并发量为 10 个不同请求标识；资料服务可记录每个请求的鉴权时刻。
        5. 可只读导出本行实际鉴权与停用日志，记录每个请求标识。

    测试步骤：
        1. 在选定网关用甲访问令牌正常读取资料，保存成功响应及有效期。
        2. 安全管理员停用甲，同时向该网关发起 10 个不同标识的资料请求，保存每个请求发起、接收、鉴权与响应时刻。
        3. 逐个区分生效前已获准的在途请求和生效后新请求；继续观察 60 秒，统计所有漏放请求及持续窗口。
        4. 账号乙正常读取资料；导出本行停用、鉴权与请求记录，按请求标识和实际时间逐项核对响应。

    预期结果：
        1. 本行真实路径在停用前可访问，所用令牌有效；不以路径不存在或令牌过期制造拒绝。
        2. 该网关在冻结上限内停止放行甲请求，已确认生效后新发起请求被拒；并发中每个漏放事实均被记录。
        3. 所有观察到的放行及其时刻均被记录，乙账号仍可正常读取自己的资料。
    """

    def test_account_deactivation_concurrent_race(
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
