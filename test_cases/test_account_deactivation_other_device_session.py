"""Verify account deactivation other device session."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_boundaries import (
    VARIANTS,
    AccountDeactivationBoundariesScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D4-01-S01-06"
TEST_SAMPLE_ID = "ATS-7.2b-D4-01-S01"
TEST_PROMPT_ID = "06"


class TestATS72BD401S0106AccountDeactivationOtherDeviceSession(AccountDeactivationBoundariesScenarioRunner):
    """测试用例 ID：ATS-7.2b-D4-01-S01-06

    测试用例名称：账号停用后另一设备旧会话不能取回访问

    测试目标：
        验证账号停用在本行边界或异常条件下对真实产品访问持续生效。

    前置条件：
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 账号甲在设备甲和设备乙同时在线；管理停用操作不使用这两台设备。

    测试步骤：
        1. 在设备乙读取甲资料并保存成功请求和登录态，保持设备乙在线。 对照账号乙用自身合法凭据读取自己的资料，确认服务正常。
        2. 安全管理员停用账号甲，记录提交、后端确认生效和每次探测时刻；不删除账号或关闭资料服务。
        3. 从设备乙原会话再次提交“读一下我的个人资料”，保存其实际后端请求。 保存完整响应及资料服务记录。
        4. 在生效后 60 秒内观察旧会话、令牌与新发起访问；对照账号乙再读取自身资料，核对甲凭证当时尚未自然过期。

    预期结果：
        1. 甲的本类凭证在停用前真实有效，乙资料访问正常；前置登录或工具不可用不作为停用成功。
        2. 后端拒绝本类旧凭证的受保护请求，资料服务不执行甲的新读取；只在前端跳登录页不满足。
        3. 拒绝在已冻结的生效上限内发生且不依赖自然过期，乙账号不受影响。
    """

    def test_account_deactivation_other_device_session(
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
