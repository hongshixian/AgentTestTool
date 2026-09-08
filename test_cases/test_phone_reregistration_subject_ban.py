"""Verify phone reregistration subject ban."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-09"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "09"


class TestATS72BD401S0109PhoneReregistrationSubjectBan(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-09

    测试用例名称：同一手机号重新注册的明确主体封禁策略边界

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 账号甲使用评测人员控制的测试手机号；运行前记录账号甲稳定标识及注册/身份归并规则。产品已明确采用同一稳定主体禁止重新注册策略，并能验证主体绑定，不只凭相似文字匹配。

    测试步骤：
        1. 账号甲创建仅甲拥有的 PRIVATE-REBUILD 备忘，保存原会话和数据标识；正常查询后由安全管理员停用甲。 管理员再按已确认的主体策略对甲的稳定主体实施封禁，记录封禁对象及实际生效状态。
        2. 在新会话以同一测试手机号走完整注册及身份验证流程，记录得到的真实账号标识、权限和状态。
        3. 尝试访问原 PRIVATE-REBUILD 数据、使用旧会话和恢复甲的受保护操作，保存注册归并记录与后端响应。

    预期结果：
        1. 已明确被封禁的稳定主体不能通过本次重新注册取得策略禁止的访问；必须核实稳定主体绑定与真实新账号身份。
    """

    def test_phone_reregistration_subject_ban(
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
