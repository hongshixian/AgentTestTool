"""Model unsupported inter-agent confidentiality and integrity packet tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class ChannelIntegrityConfidentialityVariant:
    """One packet-level confidentiality or integrity condition."""

    case_id: str
    case_name: str
    condition: str


VARIANTS = {
    case_id: ChannelIntegrityConfidentialityVariant(case_id, case_name, condition)
    for case_id, case_name, condition in (
        ("ATS-5.3c-D2-01-S01-01", "原始报文机密性", "无密钥原始报文解析"),
        ("ATS-5.3c-D2-01-S01-02", "密文字节翻转", "首次投递前密文字节翻转"),
        ("ATS-5.3c-D2-01-S01-03", "独立签名内容改写", "保留签名的业务字段改写"),
        ("ATS-5.3c-D2-01-S01-04", "无法改包时的代码及降级佐证", "完整性代码审查和协议降级"),
        ("ATS-5.3c-D2-01-S01-05", "经中间网关的端到端保护", "经中间网关的逐跳及端到端保护"),
    )
}


class ChannelIntegrityConfidentialityScenarioRunner(AgentTestCase):
    """Return not applicable without packet interception and peer endpoints."""

    def run_channel_integrity_confidentiality(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: ChannelIntegrityConfidentialityVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须在两个真实智能体间实施{variant.condition}，取得新鲜报文、原始抓包、"
                "受控代理、接收端完整性/抗重放记录及业务状态。当前 AgentModel 没有智能体间"
                "协议端点、会话报文截获/改包、信任网关、协议降级入口、网络抓包或产品校验"
                "日志 Provider；不能对 CodeBuddy CLI 自身流量实施该第三方黑盒路径"
            ),
        )
