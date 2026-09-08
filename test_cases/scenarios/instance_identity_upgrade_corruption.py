"""Model unsupported instance identity upgrade and storage-corruption paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class InstanceIdentityUpgradeCorruptionVariant:
    """One upgrade, concurrency, migration, or local corruption condition."""

    case_id: str
    case_name: str
    condition: str


VARIANTS = {
    case_id: InstanceIdentityUpgradeCorruptionVariant(case_id, case_name, condition)
    for case_id, case_name, condition in (
        ("ATS-5.1b-D4-01-S01-01", "版本升级保留历史并维持完整性校验", "版本升级保留历史并维持完整性校验"),
        ("ATS-5.1b-D4-01-S01-02", "同一实例并发计算不因标识竞态误拒", "同一实例并发计算不因标识竞态误拒"),
        ("ATS-5.1b-D4-01-S02-01", "标识存储损坏：将标识存储文件截断为原长度的一半", "标识存储损坏：将标识存储文件截断为原长度的一半"),
        ("ATS-5.1b-D4-01-S02-02", "标识存储损坏：只改写校验值而保留实例标识", "标识存储损坏：只改写校验值而保留实例标识"),
        ("ATS-5.1b-D4-01-S02-03", "标识存储损坏：在标识位置写入产品声明字符集以外的字符", "标识存储损坏：在标识位置写入产品声明字符集以外的字符"),
        ("ATS-5.1b-D4-01-S01-03", "明确迁移或重建后的实例身份与历史关联", "明确迁移或重建后的实例身份与历史关联"),
    )
}


class InstanceIdentityUpgradeCorruptionScenarioRunner(AgentTestCase):
    """Return not applicable without real instance identities and isolated versions."""

    def run_instance_identity_upgrade_corruption(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: InstanceIdentityUpgradeCorruptionVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须在专用产品设备或部署对真实实例执行{variant.condition}，读取完整实例身份、历史、"
                "授权、执行主体和校验日志。当前 CodeBuddy LocalStateController 只有外部 Helper 协议且"
                "仓库未实现真实标识存储定位/备份/损坏/重启/恢复；AgentModel 也不提供两个产品版本、"
                "升级/迁移、同一权威实例并发或双账号实例管理，不能安全实施本行路径"
            ),
        )
