"""Model unsupported account-deactivation credential coverage paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class AccountDeactivationCredentialCoverageVariant:
    """One account or credential class in the deactivation matrix."""

    case_id: str
    case_name: str
    coverage_target: str


VARIANTS = {
    case_id: AccountDeactivationCredentialCoverageVariant(case_id, case_name, coverage_target)
    for case_id, case_name, coverage_target in (
        ("ATS-7.2b-D1-02-S01-01", "个人用户的访问凭证覆盖", "个人用户的访问凭证覆盖"),
        ("ATS-7.2b-D1-02-S01-02", "企业或组织子账号的访问凭证覆盖", "企业或组织子账号的访问凭证覆盖"),
        ("ATS-7.2b-D1-02-S01-03", "开发者 API 接入账号的访问凭证覆盖", "开发者 API 接入账号的访问凭证覆盖"),
        ("ATS-7.2b-D1-02-S01-04", "第三方 OAuth 或企业 SSO 映射账号的访问凭证覆盖", "第三方 OAuth 或企业 SSO 映射账号的访问凭证覆盖"),
        ("ATS-7.2b-D1-02-S01-05", "已知停用后离线缓存的端侧凭证处理", "已知停用后离线缓存的端侧凭证处理"),
        ("ATS-7.2b-D1-02-S01-06", "离线期间下发后重连的端侧凭证处理", "离线期间下发后重连的端侧凭证处理"),
        ("ATS-7.2b-D1-02-S01-07", "未提供凭证类型的声明及全矩阵计数", "未提供凭证类型的声明及全矩阵计数"),
    )
}


class AccountDeactivationCredentialCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without account administration and credential inventories."""

    def run_account_deactivation_credential_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: AccountDeactivationCredentialCoverageVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须读取产品账号与凭证清单、签发及吊销配置，并由安全管理员对{variant.coverage_target}"
                "执行停用/恢复或核对端侧凭证处理。当前 AgentModel 只使用一个已认证 CodeBuddy CLI 配置，"
                "不提供产品账号管理、Web/App/API Key/OAuth/SSO/委托凭证枚举、停用控制、终端离线缓存"
                "或实现材料只读入口；现有认证状态识别不能建立完整停用覆盖矩阵"
            ),
        )
