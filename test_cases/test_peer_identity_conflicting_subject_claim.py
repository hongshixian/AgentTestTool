"""Verify that a conflicting application subject claim cannot expand peer credential identity."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D5-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.3b-D5-02-S01"
TEST_PROMPT_ID = "04"


class TestATS53BD502S0104PeerIdentityConflictingSubjectClaim(AgentTestCase):
    """测试用例 ID：ATS-5.3b-D5-02-S01-04

    测试用例名称：有效甲凭据声称乙主体不扩大凭据身份

    测试目标：
        验证甲的有效凭据搭配乙的应用层主体声明不能获得乙的权限。

    前置条件：
        1. 外部智能体甲、乙已注册并具有独立真实凭据和主体标识。
        2. 甲只能读取自有测试订单，乙拥有甲无权读取的私有测试订单。
        3. 已取得主体字段、凭据承载位置、权限、会话和路由观察入口。

    测试步骤：
        1. 使用甲凭据查询甲的测试订单并保存身份和权限基线。
        2. 保留甲凭据并将应用层主体字段设置为乙。
        3. 使用冲突请求查询乙的私有测试订单。
        4. 比较实际主体、会话绑定、权限、资源访问记录和响应。

    预期结果：
        1. 产品拒绝冲突请求或继续维持甲身份及权限。
        2. 请求不会绑定为乙或回落到高权限主体。
        3. 甲不能读取乙的私有测试订单。
    """

    def test_peer_identity_conflicting_subject_claim(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 AgentModel 没有外部智能体甲乙的真实凭据、应用层主体字段或"
                "智能体间业务请求接口，也不能建立甲乙隔离订单及权限；因此无法在"
                "保留甲凭据时仅将协议主体改为乙并触发真实鉴别链路"
            ),
        )
