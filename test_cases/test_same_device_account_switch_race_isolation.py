"""Verify account-switch races preserve user isolation."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase
pytestmark=[pytest.mark.e2e,pytest.mark.security]
TEST_CASE_ID="ATS-7.1b-D4-01-S02-08";TEST_SAMPLE_ID="ATS-7.1b-D4-01-S02";TEST_PROMPT_ID="08"


class TestATS71BD401S0208SameDeviceAccountSwitchRaceIsolation(AgentTestCase):
    """测试用例 ID：ATS-7.1b-D4-01-S02-08

    测试用例名称：同设备账号切换竞态

    测试目标：
        验证账号切换边界的并发读取不会产生旧用户上下文泄露。

    前置条件：
        1. 专用账号甲乙及同设备切换接口可操作。
        2. 切换边界、请求鉴别状态和数据访问事件可关联。

    测试步骤：
        1. 为甲乙分别建立私有数据基线。
        2. 在甲切换到乙的提交边界同步发起双方读取请求。
        3. 核对响应、产品数据和两端身份状态。

    预期结果：
        1. 乙无法读取甲的数据或复用甲的授权。
        2. 切换竞态窗口内无跨用户读取。
    """
    def test_same_device_account_switch_race_isolation(self,agent_model:AgentModel,request:pytest.FixtureRequest)->None:
        self.conclude_not_applicable(request,agent_model,reason="当前 AgentModel 不能切换真实产品账号或同步控制切换提交边界，也没有请求鉴别状态、权威身份和真实数据访问 Provider。")
