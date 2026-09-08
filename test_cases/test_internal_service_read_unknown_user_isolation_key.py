"""Verify internal-service reads reject an unknown user-isolation key."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D4-01-S02-05";TEST_SAMPLE_ID="ATS-7.1b-D4-01-S02";TEST_PROMPT_ID="05"


class TestATS71BD401S0205InternalServiceReadUnknownUserIsolationKey(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D4-01-S02-05

    测试用例名称：内部服务读取隔离键为不存在的用户标识

    测试目标：
        验证内部服务读取的未知用户隔离键不回落共享数据。

    前置条件：
        1. 账号甲乙私有数据和内部服务实际请求层可控制。
        2. 权威身份、对象归属及数据访问事件可查询。

    测试步骤：
        1. 建立甲乙私有数据和乙合法读取基线。
        2. 将乙内部请求的用户标识改为不存在值后重放。
        3. 核对响应、产物、访问事件和所有者数据。

    预期结果：
        1. 乙未读取甲的数据或复用甲的授权。
        2. 未知键不回落默认桶或全量数据。
    """
    def test_internal_service_read_unknown_user_isolation_key(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 无产品内部服务请求入口，不能改写用户隔离键或切换真实账号，也没有权威身份、资源和数据访问 Provider。")
