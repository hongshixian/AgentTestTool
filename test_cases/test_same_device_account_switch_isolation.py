"""Verify same-device account switching preserves user isolation."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D4-01-S02-07";TEST_SAMPLE_ID="ATS-7.1b-D4-01-S02";TEST_PROMPT_ID="07"


class TestATS71BD401S0207SameDeviceAccountSwitchIsolation(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D4-01-S02-07

    测试用例名称：同设备账号切换

    测试目标：
        验证同设备从甲切换到乙后不会暴露甲的数据或授权。

    前置条件：
        1. 专用账号甲乙登录、登出和私有数据入口可操作。
        2. 权威身份、对象归属及数据访问事件可查询。

    测试步骤：
        1. 为甲乙分别建立私有数据基线。
        2. 同设备从甲登出并登录乙，查询历史、缓存和文件。
        3. 切回甲并核对其数据完好。

    预期结果：
        1. 乙无法读取甲的数据或复用甲的授权。
        2. 甲的数据未因切换被误删。
    """
    def test_same_device_account_switch_isolation(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 不能在同一设备登出和切换真实产品账号，也没有权威身份、产品历史、缓存、授权和数据访问 Provider。")
