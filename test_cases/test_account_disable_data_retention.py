"""Verify historical data retention after account disablement."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-02-S01-06"
TEST_SAMPLE_ID = "ATS-7.2b-D2-02-S01"
TEST_PROMPT_ID = "06"


class TestATS72BD202S0106AccountDisableDataRetention(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-02-S01-06

    测试用例名称：历史数据与记录保留

    测试目标：
        验证历史数据与记录保留。

    前置条件:
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 审计员可查询账号甲的数据与历史记录但不替甲执行普通业务；甲的旧会话和令牌运行前保存在受控凭据区。

    测试步骤:
        1. 账号甲创建测试备忘 KEEP-ACCOUNT-甲并读取个人资料，记录数据标识、任务记录和当前有效会话。
        2. 安全管理员停用甲而不删除数据；审计员查询 KEEP-ACCOUNT-甲和历史任务记录，同时乙正常读取自身资料。
        3. 核对停用状态、数据内容及操作日志，不恢复账号。
        4. 导出账号状态流转和本行访问结果，核对所有数据仍归甲所有。

    预期结果:
        1. 停用不删除 KEEP-ACCOUNT-甲及历史记录，审计员可按权限核查，乙正常访问；审计员读到保留数据不等于甲仍可登录。
        2. 账号处于真实停用状态，停用操作和数据保留事实一致。
    """

    def test_account_disable_data_retention(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有服务商管理员账号停用和恢复入口，"
                "也不能控制 API Key、OAuth/SSO、审计员或后台任务的真实账号状态"
            ),
        )
