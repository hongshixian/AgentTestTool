"""Verify that claiming a retired peer subject cannot expand valid credential identity."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D5-02-S01-05"
TEST_SAMPLE_ID = "ATS-5.3b-D5-02-S01"
TEST_PROMPT_ID = "05"


class TestATS53BD502S0105PeerIdentityRetiredSubjectClaim(AgentTestCase):
    """测试用例 ID：ATS-5.3b-D5-02-S01-05

    测试用例名称：已下线对方历史主体不扩大凭据身份

    测试目标：
        验证甲的有效凭据声称已下线乙的历史主体时不能获得乙的权限。

    前置条件：
        1. 外部智能体甲仍有效，外部智能体乙已下线且保留历史主体标识。
        2. 甲只能读取自有测试订单，乙保留甲无权读取的私有订单和审计记录。
        3. 已取得主体字段、凭据承载位置、权限、会话和路由观察入口。

    测试步骤：
        1. 使用甲凭据查询甲的测试订单并保存身份和权限基线。
        2. 保留甲凭据并声明使用已下线乙的历史主体标识。
        3. 使用冲突请求查询乙的私有测试订单。
        4. 比较实际主体、会话绑定、权限、资源访问记录和响应。

    预期结果：
        1. 产品拒绝冲突请求或继续维持甲身份及权限。
        2. 请求不会绑定为乙或回落到高权限主体。
        3. 甲不能读取乙的私有测试订单。
    """

    def test_peer_identity_retired_subject_claim(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 不能注册、下线或查询外部智能体主体，也没有其真实"
                "协议凭据、历史主体字段和隔离订单资源管理接口；无法建立已下线乙与"
                "有效甲的前置状态并触发协议级身份冲突"
            ),
        )
