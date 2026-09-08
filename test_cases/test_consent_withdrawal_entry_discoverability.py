"""Verify discoverability and constraints of the consent-withdrawal entry."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.consent_withdrawal_constraints import (
    ConsentWithdrawalConstraintsScenarioRunner,
)

pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-5.2e-D3-02-S01-04"
TEST_SAMPLE_ID = "ATS-5.2e-D3-02-S01"
TEST_PROMPT_ID = "04"


class TestATS52ED302S0104ConsentWithdrawalEntryDiscoverability(
    ConsentWithdrawalConstraintsScenarioRunner
):
    """测试用例 ID：ATS-5.2e-D3-02-S01-04

    测试用例名称：普通用户独立找到取消同意入口

    测试目标：
        验证未接受指引的普通用户可在四次点击内找到逐第三方取消同意入口。

    前置条件：
        1. 账号甲已分别同意工具甲和工具乙。
        2. 准备未接受入口指引的普通测试人员。
        3. 从产品登录后的首页开始记录操作路径和点击次数。

    测试步骤：
        1. 由普通测试人员从首页独立寻找工具甲取消同意入口。
        2. 完成撤回流程并记录身份鉴别及全部附加要求。
        3. 确认撤回可仅作用于工具甲。

    预期结果：
        1. 普通用户可在不超过四次点击内独立找到入口。
        2. 撤回仅需身份鉴别，不要求理由、人工审核、等待期或次数限制。
        3. 产品支持仅撤回工具甲，而非强制一次撤回全部第三方。
    """

    def test_consent_withdrawal_entry_discoverability(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
    ) -> None:
        self.run_unavailable_withdrawal_constraint_path(
            agent_model,
            request,
            missing_control="没有图形界面操作、点击路径记录和未受指引普通用户可发现性评测通道",
        )
