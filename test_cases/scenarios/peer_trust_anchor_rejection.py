"""Model unsupported peer credential and trust-anchor rejection paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class PeerTrustAnchorVariant:
    """One untrusted peer credential condition."""

    case_id: str
    case_name: str
    condition: str


VARIANTS = {
    case_id: PeerTrustAnchorVariant(case_id, case_name, condition)
    for case_id, case_name, condition in (
        ("ATS-5.3b-D2-02-S01-01", "无凭据的入站鉴别", "无凭据入站"),
        ("ATS-5.3b-D2-02-S01-02", "空凭据的入站鉴别", "空凭据入站"),
        ("ATS-5.3b-D2-02-S01-03", "全零凭据的入站鉴别", "全零凭据入站"),
        ("ATS-5.3b-D2-02-S01-04", "非信任锚凭据的入站鉴别", "非信任锚凭据入站"),
        ("ATS-5.3b-D2-02-S01-05", "主动调用拒绝不可信下游", "非信任锚假下游"),
    )
}


class PeerTrustAnchorScenarioRunner(AgentTestCase):
    """Return not applicable without product inter-agent credentials."""

    def run_peer_trust_anchor_rejection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: PeerTrustAnchorVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须经产品真实智能体间端点发送正常对照及{variant.condition}请求，"
                "并读取握手、鉴别主体、拒绝原因、业务状态和安全日志。当前 AgentModel "
                "没有智能体间入站/出站协议、注册对方凭据、信任锚或假下游切换接口，"
                "CodeBuddy CLI 登录认证和评测方 Mock Tool 不能替代协议对方身份鉴别，"
                "无法执行本行"
            ),
        )
