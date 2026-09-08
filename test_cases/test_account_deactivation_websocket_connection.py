"""Verify account deactivation websocket connection."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-05"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "05"


class TestATS72BD401S0105AccountDeactivationWebsocketConnection(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-05

    测试用例名称：WebSocket长连接随账号停用停止

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 本产品支持 WebSocket 进度连接，连接归账号甲；接收端可记录每个业务事件的生成时间和到达时间，控制关闭事件与业务数据分开记录。

    测试步骤：
        1. 账号甲启动“每隔 2 秒上报一次进度”的长任务并保持进度连接，确认收到多个不同序号；账号乙独立任务作为对照。
        2. 安全管理员停用甲，不关闭整个进度服务；记录后端生效时刻。
        3. 观察 60 秒的 WebSocket 关闭状态、业务消息和后端任务请求，区分停用前生成但迟到的消息与停用后新产生的业务消息。

    预期结果：
        1. 甲的 WebSocket 业务连接在停用上限内被主动结束，后端不再为其产生新业务操作，不能等待连接自然结束；乙连接正常。
    """

    def test_account_deactivation_websocket_connection(
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
