"""Verify account deactivation valid token."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-02"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "02"


class TestATS72BD401S0102AccountDeactivationValidToken(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-02

    测试用例名称：令牌仍在有效期下的账号停用

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 本行只使用甲的一枚新签发访问令牌；它的自然到期时间晚于停用上限加 60 秒。
        5. 可只读导出本行实际鉴权与停用日志，记录每个请求标识。

    测试步骤：
        1. 用这枚访问令牌正常读取甲资料，记录签发时间、真实到期时间与成功响应。
        2. 在该令牌远未到期时停用甲，保持同一令牌和同一资料接口，持续记录首次拒绝时刻。
        3. 观察到停用上限后的 60 秒，对比首次拒绝、后端停用状态和令牌自然到期时间，排除因令牌到期造成的拒绝。
        4. 账号乙正常读取资料；导出本行停用、鉴权与请求记录，按请求标识和实际时间逐项核对响应。

    预期结果：
        1. 本行真实路径在停用前可访问，所用令牌有效；不以路径不存在或令牌过期制造拒绝。
        2. 令牌在冻结上限内被主动撤销或随账号状态被拒绝，拒绝发生在自然到期之前，不能坐等过期。
        3. 所有观察到的放行及其时刻均被记录，乙账号仍可正常读取自己的资料。
    """

    def test_account_deactivation_valid_token(
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
