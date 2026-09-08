"""Verify OAuth token revocation after account disablement."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D2-02-S01-02"
TEST_SAMPLE_ID = "ATS-7.2b-D2-02-S01"
TEST_PROMPT_ID = "02"


class TestATS72BD202S0102AccountDisableOAuthTokenRevocation(AgentTestCase):
    """测试用例 ID：ATS-7.2b-D2-02-S01-02

    测试用例名称：账号停用后OAuth 授权令牌不能取回访问

    测试目标：
        验证账号停用后OAuth 授权令牌不能取回访问。

    前置条件:
        1. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        2. 评测账号甲与对照账号乙属于同一测试服务且数据隔离，各自有只读测试个人档案，分别含 PROFILE-甲 和 PROFILE-乙 标记。资料服务独立记录账号、请求、时间和结果。
        3. 技术负责人运行前冻结停用目标账号标识、后端生效状态和产品承诺的时延上限；采集从停用前到生效后 60 秒的请求与状态。旧凭证的自然有效期须覆盖该窗口，不用过期凭证作对照。
        4. 账号甲通过真实测试 OAuth 客户端授权访问本服务；令牌的资源范围限本服务账号甲。

    测试步骤:
        1. 通过正常 OAuth 授权取得有效令牌，用它访问本服务账号甲资料并保存成功报文。 对照账号乙用自身合法凭据读取自己的资料，确认服务正常。
        2. 安全管理员停用账号甲，记录提交、后端确认生效和每次探测时刻；不删除账号或关闭资料服务。
        3. 用停用前的同一 OAuth 令牌调用本服务受保护资料接口，不要求关闭第三方身份提供商。 保存完整响应及资料服务记录。
        4. 在生效后 60 秒内观察旧会话、令牌与新发起访问；对照账号乙再读取自身资料，核对甲凭证当时尚未自然过期。

    预期结果:
        1. 甲的本类凭证在停用前真实有效，乙资料访问正常；前置登录或工具不可用不作为停用成功。
        2. 后端拒绝本类旧凭证的受保护请求，资料服务不执行甲的新读取；只在前端跳登录页不满足。
        3. 拒绝在已冻结的生效上限内发生且不依赖自然过期，乙账号不受影响。
    """

    def test_account_disable_oauth_token_revocation(
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
