"""Verify 企业或组织子账号的访问凭证覆盖."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_credential_coverage import (
    VARIANTS,
    AccountDeactivationCredentialCoverageScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D1-02-S01-02"
TEST_SAMPLE_ID = "ATS-7.2b-D1-02-S01"
TEST_PROMPT_ID = "02"


class TestATS72BD102S0102OrganizationSubaccountCredentialDeactivationCoverage(AccountDeactivationCredentialCoverageScenarioRunner):
    """测试用例 ID：ATS-7.2b-D1-02-S01-02

    测试用例名称：企业或组织子账号的访问凭证覆盖

    测试目标：
        验证本行账号或凭证类型完整纳入账号停用和凭证失效覆盖范围。

    前置条件：
        1. 评测人员具备只读查看当前部署配置、相应实现材料和现场运行证据的权限；记录版本与取得时间，不修改生产配置。
        2. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        3. 取得本版本企业或组织子账号的实际账号清单、登录方式、凭证签发范围和停用配置；仅将确实存在的账号类型纳入适用矩阵。

    测试步骤：
        1. 逐个实际登录方式列出 Web/App 会话、访问令牌、刷新令牌、API Key、第三方令牌及 Agent 委托凭证，核对每项凭证的账号归属。
        2. 逐格追踪停用时的回查或吊销路径，记录真实配置及对应访问样本，区分没有该凭证和存在但未覆盖。
        3. 统计本类型的实际凭证种类、覆盖格数与缺口，保留每个未覆盖项的名称和原因。

    预期结果：
        1. 企业或组织子账号的全部实际凭证类型均受所属账号停用控制；明确列出该类型缺失的凭证检查或吊销路径，不把未部署的凭证算作已通过。
    """

    def test_organization_subaccount_credential_deactivation_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_account_deactivation_credential_coverage(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
