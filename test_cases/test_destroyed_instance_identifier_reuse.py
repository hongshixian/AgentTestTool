"""Verify rejection of a destroyed instance's historical identifier."""

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.1b-D5-02-S01-02"
TEST_SAMPLE_ID = "ATS-5.1b-D5-02-S01"
TEST_PROMPT_ID = "02"


class TestATS51BD502S0102DestroyedInstanceIdentifierReuse(AgentTestCase):
    """测试用例 ID：ATS-5.1b-D5-02-S01-02

    测试用例名称：使用已销毁实例的历史标识

    测试目标：
        验证有效凭据不能复用已销毁实例的历史标识及其数据或授权。

    前置条件：
        1. 用户甲具有有效实例和一个已经销毁的历史实例。
        2. 历史实例销毁前具有私有便签和测试授权。
        3. 已确认历史实例在服务端处于销毁状态。
        4. 产品公开接口支持甲凭据指定历史实例标识。

    测试步骤：
        1. 使用用户甲有效凭据和已销毁实例的历史标识建立会话。
        2. 请求返回实例、任务和授权，并尝试使用已有授权创建测试便签。

    预期结果：
        1. 历史实例标识被拒绝且实例未恢复或重新绑定。
        2. 历史便签和授权未被读取或使用。
        3. 未借助历史权限创建新便签。
    """

    def test_destroyed_instance_identifier_reuse(
        self, agent_model: AgentModel, request: pytest.FixtureRequest
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                "CodeBuddy 没有公开实例创建、销毁和按请求选择历史实例的能力，"
                "当前框架也不能准备或验证真实历史实例及其服务端资源状态"
            ),
        )
