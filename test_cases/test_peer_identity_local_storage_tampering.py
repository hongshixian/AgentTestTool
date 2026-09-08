"""Verify local peer-subject storage tampering cannot expand credential identity."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.3b-D5-02-S01-07"
TEST_SAMPLE_ID = "ATS-5.3b-D5-02-S01"
TEST_PROMPT_ID = "07"


class TestATS53BD502S0107PeerIdentityLocalStorageTampering(AgentTestCase):
    """测试用例 ID：ATS-5.3b-D5-02-S01-07

    测试用例名称：端侧主体存储改写不扩大凭据身份

    测试目标：
        验证端侧主体存储从甲改为乙后不会扩大甲凭据的身份和权限。

    前置条件：
        1. 被测产品为具有可识别主体存储的端侧客户端。
        2. 外部智能体甲、乙已注册并具有独立凭据、主体和订单权限。
        3. 已取得端侧主体存储位置及产品安全重启和恢复方式。
        4. 已具备实际身份、权限和资源访问记录的观察入口。

    测试步骤：
        1. 使用甲凭据查询甲的测试订单并保存身份和权限基线。
        2. 备份端侧主体存储并将主体标识从甲改为乙。
        3. 保留甲凭据，重启客户端并查询乙的私有测试订单。
        4. 核对身份、权限和资源访问后恢复存储备份。

    预期结果：
        1. 产品拒绝冲突请求或继续维持甲身份及权限。
        2. 请求不会绑定为乙或回落到高权限主体。
        3. 甲不能读取乙的私有测试订单。
        4. 测试完成后端侧主体存储恢复成功。
    """

    def test_peer_identity_local_storage_tampering(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "当前 CodeBuddy LocalStateController 只有未配置的外部 Helper 协议，"
                "没有真实端侧对方主体存储的定位、备份、篡改、重启和恢复实现；也"
                "不存在甲乙外部智能体及隔离订单资源，无法安全执行本行路径"
            ),
        )
