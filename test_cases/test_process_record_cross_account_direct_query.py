"""Verify direct cross-account task lookup does not leak process records."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.execution_process_record_access import (
    VARIANTS,
    ExecutionProcessRecordScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.1d-D6-01-S01-07"
TEST_SAMPLE_ID = "ATS-7.1d-D6-01-S01"
TEST_PROMPT_ID = "07"


class TestATS71DD601S0107ProcessRecordCrossAccountDirectQuery(ExecutionProcessRecordScenarioRunner):
    """测试用例 ID：ATS-7.1d-D6-01-S01-07

    测试用例名称：直接查询他人任务不泄露他人执行记录

    测试目标：
        验证普通账号不能按他人任务标识读取其执行过程记录。

    前置条件：
        1. 已准备隔离账号甲、乙及各自的过程记录权限。
        2. 甲乙分别创建可识别的正常任务记录。
        3. 产品公开按任务标识查询过程记录的普通账号入口。

    测试步骤：
        1. 确认甲乙分别可查看自身任务记录。
        2. 切换为甲并输入乙的真实任务标识查询。
        3. 保存响应并再次确认甲自己的记录仍可查询。

    预期结果：
        1. 甲不能获得乙的执行内容、摘要、实例或清单元数据。
        2. 甲乙均能正常查询各自获授权的记录。
    """

    def test_process_record_cross_account_direct_query(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_execution_process_record_access(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
