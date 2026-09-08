"""Verify integrity protection for an instance identifier stored in local preferences."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-02-S03-02"
TEST_SAMPLE_ID = "ATS-5.1b-D5-02-S03"
TEST_PROMPT_ID = "02"


class TestATS51BD502S0302LocalPreferenceInstanceIdentifierTampering(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-02-S03-02

    测试用例名称：篡改端侧偏好存储实例标识

    测试目标：
        验证修改客户端偏好存储中的实例标识不能取得其他实例的数据或授权。

    前置条件：
        1. 用户甲、乙及其隔离实例、资源和授权已准备。
        2. 已定位产品实际使用的偏好存储实例标识项。
        3. 可安全备份、修改、重启并恢复测试客户端。
        4. 可查询真实实例、资源访问和授权使用记录。

    测试步骤：
        1. 备份并关闭客户端后仅将偏好存储实例标识从甲改为乙。
        2. 重启客户端并请求读取实例资源和使用已有授权。
        3. 完成取证后恢复配置并验证原实例可用。

    预期结果：
        1. 客户端重新鉴别或服务端拒绝修改后的实例标识。
        2. 未取得实例乙或旧实例的数据和授权。
        3. 新分配实例只归属于用户甲且不继承旧数据或授权。
    """

    def test_local_preference_instance_identifier_tampering(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "仓库没有端侧偏好存储的真实产品适配，无法定位、修改、重启和恢复被测客户端，"
                "也不能证明修改项与服务端实例身份的实际关联"
            ),
        )
