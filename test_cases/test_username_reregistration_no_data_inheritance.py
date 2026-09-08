"""Verify username re-registration does not inherit deleted-account data."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D4-01-S01-02";TEST_SAMPLE_ID="ATS-7.1b-D4-01-S01";TEST_PROMPT_ID="02"


class TestATS71BD401S0102UsernameReregistrationNoDataInheritance(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D4-01-S01-02

    测试用例名称：测试用户名注销再注册不继承

    测试目标：
        验证同一用户名重新注册的新用户不继承已注销账号数据和授权。

    前置条件：
        1. 专用账号创建、注销、再注册及私有数据管理入口可操作。
        2. 权威身份、对象归属、数据访问和安全事件可查询。

    测试步骤：
        1. 为账号甲和乙分别建立私有数据基线。
        2. 注销甲并用同一用户名注册甲新。
        3. 由甲新查询旧记忆、任务和文件并核对访问事件。

    预期结果：
        1. 甲新无法读取甲的历史数据或复用甲的授权。
        2. 正常自有数据访问保持可用。
    """
    def test_username_reregistration_no_data_inheritance(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 不能创建、注销或以同一用户名重新注册产品账号，也没有权威身份、对象归属、授权和真实数据访问 Provider。")
