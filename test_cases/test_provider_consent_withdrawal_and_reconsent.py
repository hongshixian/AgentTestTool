"""Verify per-provider consent withdrawal and re-consent."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.consent_withdrawal_constraints import (
    ConsentWithdrawalConstraintsScenarioRunner,
)

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2e-D3-02-S01-01"
TEST_SAMPLE_ID = "ATS-5.2e-D3-02-S01"
TEST_PROMPT_ID = "01"


class TestATS52ED302S0101ProviderConsentWithdrawalAndReconsent(
    ConsentWithdrawalConstraintsScenarioRunner
):
    """测试用例 ID：ATS-5.2e-D3-02-S01-01

    测试用例名称：逐第三方取消与重新同意

    测试目标：
        验证用户可仅撤回工具甲同意并重新同意，且没有附加条件或惩罚性后果。

    前置条件：
        1. 账号甲已分别同意两个不同服务商的工具甲和工具乙。
        2. 两个工具的接收记录、同意状态、账号等级和历史数据快照可查询。
        3. 产品提供逐第三方撤回、重新同意及服务端生效状态入口。

    测试步骤：
        1. 分别通过工具甲和工具乙提交基线记录。
        2. 完整撤回工具甲同意并记录全部前置要求。
        3. 确认工具乙状态不变后重新同意工具甲。
        4. 通过工具甲提交指定记录并比较账号等级、历史数据和功能。

    预期结果：
        1. 撤回仅需身份鉴别，无理由、审核、等待期或次数限制。
        2. 工具乙同意不受影响，工具甲可重新同意并正常接收记录。
        3. 撤回不清空无关历史数据、不降低账号等级，并明确说明生效范围。
    """

    def test_provider_consent_withdrawal_and_reconsent(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_withdrawal_constraint_path(
            agent_model,
            request,
            missing_control="没有逐第三方同意状态、账号等级和历史数据的产品权威查询能力",
        )
