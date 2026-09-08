"""Verify email reregistration data boundary."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-10"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "10"


class TestATS72BD401S0110EmailReregistrationDataBoundary(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-10

    测试用例名称：同一邮箱重新注册的原账号数据与会话边界

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 账号甲使用评测人员控制的测试邮箱；运行前记录账号甲稳定标识及注册/身份归并规则。本行只验证原被停账号的访问和数据隔离，不预设禁止创建所有新账号。

    测试步骤：
        1. 账号甲创建仅甲拥有的 PRIVATE-REBUILD 备忘，保存原会话和数据标识；正常查询后由安全管理员停用甲。
        2. 在新会话以同一测试邮箱走完整注册及身份验证流程，记录得到的真实账号标识、权限和状态。
        3. 尝试访问原 PRIVATE-REBUILD 数据、使用旧会话和恢复甲的受保护操作，保存注册归并记录与后端响应。

    预期结果：
        1. 新注册不能继承原被停账号的旧会话、凭证或未经重新授权的数据访问；独立新账号的普通功能可用不自动等于甲恢复。
    """

    def test_email_reregistration_data_boundary(
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
