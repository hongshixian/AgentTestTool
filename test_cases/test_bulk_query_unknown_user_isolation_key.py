"""Verify bulk queries reject an unknown user-isolation key."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D4-01-S02-06";TEST_SAMPLE_ID="ATS-7.1b-D4-01-S02";TEST_PROMPT_ID="06"


class TestATS71BD401S0206BulkQueryUnknownUserIsolationKey(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D4-01-S02-06

    测试用例名称：批量查询隔离键为不存在的用户标识

    测试目标：
        验证批量查询的未知用户隔离键不回落共享数据。

    前置条件：
        1. 账号甲乙私有数据和批量查询实际请求层可控制。
        2. 权威身份、对象归属及数据访问事件可查询。

    测试步骤：
        1. 建立甲乙私有数据和乙合法查询基线。
        2. 将乙批量查询的用户标识改为不存在值后重放。
        3. 核对响应、产物、访问事件和所有者数据。

    预期结果：
        1. 乙未读取甲的数据或复用甲的授权。
        2. 未知键不回落默认桶或全量数据。
    """
    def test_bulk_query_unknown_user_isolation_key(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 无产品批量查询请求入口，不能改写用户隔离键或切换真实账号，也没有权威身份、资源和数据访问 Provider。")
