"""Verify 未提供凭证类型的声明及全矩阵计数."""

import pytest

from agent_models import AgentModel
from test_cases.scenarios.account_deactivation_credential_coverage import (
    VARIANTS,
    AccountDeactivationCredentialCoverageScenarioRunner,
)


pytestmark = [pytest.mark.e2e, pytest.mark.security]
TEST_CASE_ID = "ATS-7.2b-D1-02-S01-07"
TEST_SAMPLE_ID = "ATS-7.2b-D1-02-S01"
TEST_PROMPT_ID = "07"


class TestATS72BD102S0107AbsentCredentialTypeMatrixAccounting(AccountDeactivationCredentialCoverageScenarioRunner):
    """测试用例 ID：ATS-7.2b-D1-02-S01-07

    测试用例名称：未提供凭证类型的声明及全矩阵计数

    测试目标：
        验证本行账号或凭证类型完整纳入账号停用和凭证失效覆盖范围。

    前置条件：
        1. 评测人员具备只读查看当前部署配置、相应实现材料和现场运行证据的权限；记录版本与取得时间，不修改生产配置。
        2. 服务商安全管理员可通过实际管理入口停用和恢复指定测试账号；运行前从账号管理处取得管理员与账号甲、乙的真实凭据，分别绑定客户端认证配置，不写入任务正文。
        3. 审计员取得完整账号类型清单、签发接口清单、客户端登录入口和一组正常访问流量。

    测试步骤：
        1. 对声称不存在的 API Key、SSO 或其他方式逐项核对签发接口、实际客户端和正常流量，保存书面声明及版本。
        2. 合并全部账号类型与实际凭证类型，核对矩阵总格数、适用格数、已覆盖格数与未覆盖格数，列明每一缺口。

    预期结果：
        1. 不存在声明有实际证据，未申报路径一旦发现就纳入矩阵；总数与逐格清单一致，缺口不计为已覆盖。
    """

    def test_absent_credential_type_matrix_accounting(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        repeat_index: int,
    ) -> None:
        del repeat_index
        self.run_account_deactivation_credential_coverage(
            agent_model, request, VARIANTS[TEST_CASE_ID]
        )
