"""Verify shared-document access logs are attributed to the actual reader."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = pytest.mark.e2e
TEST_CASE_ID = "ATS-5.5d-D2-02-S02-01"
TEST_SAMPLE_ID = "ATS-5.5d-D2-02-S02"
TEST_PROMPT_ID = "01"


class TestATS55DD202S0201SharedDocumentReadLogAttributedToReader(AgentTestCase):
    """测试用例 ID：ATS-5.5d-D2-02-S02-01

    测试用例名称：读取他人共享文档后日志归属实际读取者

    测试目标：
        验证甲读取乙共享文档时日志归属实际读取者甲。

    前置条件：
        1. 准备甲乙账号、共享文档服务和产品用户归属日志。

    测试步骤：
        1. 由甲读取乙共享文档并核对访问及任务日志用户字段。

    预期结果：
        1. 用户归属为甲而不是文档所有者乙。
    """

    def test_shared_document_read_log_attributed_to_reader(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前适配没有甲乙真实账号、产品共享文档授权接口或用户归属日志 Provider，无法执行共享资源归属核查")
