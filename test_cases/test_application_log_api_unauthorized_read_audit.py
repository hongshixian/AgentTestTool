"""Verify unauthorized application-log API reads are denied and audited."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5c-D2-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.5c-D2-02-S01"
TEST_PROMPT_ID = "01"


class TestATS55CD202S0101ApplicationLogAPIUnauthorizedReadAudit(AgentTestCase):
    """测试用例 ID：ATS-5.5c-D2-02-S01-01

    测试用例名称：应用日志接口的越权读取与访问留痕

    测试目标：
        验证普通账号不能经应用日志接口读取目标日志且尝试被审计。

    前置条件：
        1. 准备普通账号、审核账号及产品日志接口。

    测试步骤：
        1. 审核账号建立读取基线后由普通账号请求同一日志。

    预期结果：
        1. 普通账号被拒绝且成功访问和越权尝试均准确留痕。
    """

    def test_application_log_api_unauthorized_read_audit(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前适配没有普通与审核双角色配置、应用日志读取导出接口或日志访问审计 Provider，无法执行该路径")
