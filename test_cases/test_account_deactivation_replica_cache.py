"""Verify account deactivation replica cache."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-03"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "03"


class TestATS72BD401S0103AccountDeactivationReplicaCache(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-03

    测试用例名称：多副本与缓存同步下的账号停用

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 取得全部实际网关/区域节点及真实路由方法；单节点产品仍检查该节点鉴权缓存，读取缓存有效期与状态传播日志。
        5. 可只读导出本行实际鉴权与停用日志，记录每个请求标识。

    测试步骤：
        1. 用甲的当前有效令牌在每个实际节点分别正常读取资料，保存节点身份和成功响应。
        2. 安全管理员停用甲，随即在全部实际节点使用同一有效令牌发起资料请求，保留各节点响应。
        3. 逐节点观察到停用上限后的 60 秒，记录首次拒绝和最坏传播时间，核对缓存有效期及更新事件。
        4. 账号乙正常读取资料，导出停用传播、缓存和请求日志，与实际响应逐项核对。

    预期结果：
        1. 本行真实路径在停用前可访问，所用令牌有效；不以路径不存在或令牌过期制造拒绝。
        2. 全部实际节点在冻结上限内拒绝甲凭证，缓存不把放行延伸到上限之外；无地域盲区，不用平均值掩盖最慢节点。
        3. 所有观察到的放行及其时刻均被记录，乙账号仍可正常读取自己的资料。
    """

    def test_account_deactivation_replica_cache(
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
