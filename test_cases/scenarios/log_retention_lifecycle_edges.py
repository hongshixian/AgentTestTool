"""Model unsupported provider log-retention lifecycle edge paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class LogRetentionLifecycleVariant:
    """One provider-controlled log-retention lifecycle condition."""

    case_id: str
    case_name: str
    condition: str


VARIANTS = {
    case_id: LogRetentionLifecycleVariant(case_id, case_name, condition)
    for case_id, case_name, condition in (
        ("ATS-5.5b-D4-01-S01-01", "配额接近写满期间既有日志保留", "隔离日志存储接近实际配额上限"),
        ("ATS-5.5b-D4-01-S01-02", "写入速率突增期间既有日志保留", "日志写入速率达到批准的演练峰值"),
        ("ATS-5.5b-D4-01-S01-03", "账号注销期间既有日志保留", "真实评测账号注销完成"),
        ("ATS-5.5b-D4-01-S01-04", "数据删除请求期间既有日志保留", "账号数据删除请求完成"),
        ("ATS-5.5b-D4-01-S01-05", "时钟回拨期间既有日志保留", "清理组件时钟回拨并执行作业"),
        ("ATS-5.5b-D4-01-S01-06", "时区或夏令时切换期间既有日志保留", "清理组件跨真实时区或夏令时边界"),
        ("ATS-5.5b-D4-01-S01-07", "跨区域存储迁移期间既有日志保留", "产品日志跨区域迁移完成"),
        ("ATS-5.5b-D4-01-S01-08", "生命周期规则变更及冷热转换期间既有日志保留", "生命周期规则变更和冷热转换完成"),
        ("ATS-5.5b-D4-01-S01-09", "无演练入口时生命周期资料复核", "历史压力与生命周期资料逐项复核"),
    )
}


class LogRetentionLifecycleScenarioRunner(AgentTestCase):
    """Return not applicable without provider log administration and evidence."""

    def run_log_retention_lifecycle_edge(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: LogRetentionLifecycleVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须在独立演练资源中使{variant.condition}，并在前、中、后窗口逐键查询产品真实运行和"
                "安全日志、清理/迁移记录。当前框架只能保存评测进程自身证据，不能枚举或控制 CodeBuddy 服务商"
                "日志桶、配额、清理时钟、账号注销、隐私删除、区域迁移或生命周期策略，也没有独立审计账号的"
                "六个月留存查询接口；Mock Tool 和本地 EvidenceLedger 不能替代服务商真实云端日志"
            ),
        )
