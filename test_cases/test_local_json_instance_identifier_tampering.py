"""Verify integrity protection for an instance identifier stored in local JSON."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-02-S03-01"
TEST_SAMPLE_ID = "ATS-5.1b-D5-02-S03"
TEST_PROMPT_ID = "01"


class TestATS51BD502S0301LocalJsonInstanceIdentifierTampering(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-02-S03-01

    测试用例名称：篡改本地 JSON 实例标识

    测试目标：
        验证修改客户端 JSON 中的实例标识不能取得其他实例的数据或授权。

    前置条件：
        1. 用户甲、乙及其隔离实例、资源和授权已准备。
        2. 已定位产品实际使用的 JSON 实例标识配置项。
        3. 可安全备份、修改、重启并恢复测试客户端。
        4. 可查询真实实例、资源访问和授权使用记录。

    测试步骤：
        1. 备份并关闭客户端后仅将 JSON 实例标识从甲改为乙。
        2. 重启客户端并请求读取实例资源和使用已有授权。
        3. 完成取证后恢复配置并验证原实例可用。

    预期结果：
        1. 客户端重新鉴别或服务端拒绝修改后的实例标识。
        2. 未取得实例乙或旧实例的数据和授权。
        3. 新分配实例只归属于用户甲且不继承旧数据或授权。
    """

    def test_local_json_instance_identifier_tampering(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "仓库只定义 CodeBuddy 本地状态 Helper 协议，未提供定位并修改产品实际实例字段、"
                "重启和恢复的实现，也不能证明该字段被产品使用"
            ),
        )
