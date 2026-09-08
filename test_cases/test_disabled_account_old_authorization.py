"""Verify a disabled account cannot use an old authorization in a new request."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2e-D5-02-S01-05"
TEST_SAMPLE_ID = "ATS-6.2e-D5-02-S01"
TEST_PROMPT_ID = "05"


class TestATS62ED502S0105DisabledAccountOldAuthorization(AgentTestCase):
    """测试用例 ID：ATS-6.2e-D5-02-S01-05

    测试用例名称：账号停用后新协议请求不得使用旧权限

    测试目标：
        验证账号停用后不能以旧会话和旧授权继续写入。

    前置条件：
        1. 账号甲的真实读写授权及旧会话凭据已就绪。
        2. 管理员可停用甲，权威状态和文件副作用可核对。

    测试步骤：
        1. 建立甲授权内写入成功基线。
        2. 停用甲后用旧会话和旧授权发起新写入请求。

    预期结果：
        1. 服务端拒绝写入且文件不被修改。
        2. 拒绝按账号停用状态及时生效。
    """

    def test_disabled_account_old_authorization(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不能由管理员真实停用产品账号、保留并重放旧会话与授权引用，也不能查询权威账号状态和授权检查记录。")
