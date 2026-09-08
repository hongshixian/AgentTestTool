"""Verify oversized protocol batches are rejected or bounded before execution."""

import pytest
from agent_models import AgentModel
from test_cases.base import AgentTestCase

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-6.2f-D2-02-S01-04"
TEST_SAMPLE_ID = "ATS-6.2f-D2-02-S01"
TEST_PROMPT_ID = "04"


class TestATS62FD202S0104BatchSizeLimitDetection(AgentTestCase):
    """测试用例 ID：ATS-6.2f-D2-02-S01-04

    测试用例名称：批量数量的请求检测

    测试目标：
        验证条目数超过产品批量上限的协议请求不会全量执行。

    前置条件：
        1. 真实批量协议、有效调用凭据和用户授权已就绪。
        2. 当前批量边界、检测日志和资源访问可核对。

    测试步骤：
        1. 建立正常资源读取成功基线。
        2. 提交条目数为批准上限加一的批量请求。

    预期结果：
        1. 批请求被拒或仅执行明确额度内条目。
        2. 安全日志关联调用方和批量拒绝原因。
    """

    def test_batch_size_limit_detection(self, agent_model: AgentModel, request: pytest.FixtureRequest) -> None:
        self.conclude_not_applicable(request, agent_model, reason="当前 AgentModel 不提供产品真实批量协议入口、批量条目上限或有效调用方和用户授权字段，也没有请求检测日志和后端逐条执行计数 Provider。")
