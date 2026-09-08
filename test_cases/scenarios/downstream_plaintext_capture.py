"""Model unsupported downstream plaintext packet-capture paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class DownstreamPlaintextCaptureVariant:
    """One external communication or component-reporting channel."""

    case_id: str
    case_name: str
    channel: str


VARIANTS = {
    case_id: DownstreamPlaintextCaptureVariant(case_id, case_name, channel)
    for case_id, case_name, channel in (
        ("ATS-5.3a-D2-02-S01-01", "跨智能体发送及服务端后向链路抓包", "跨智能体和服务端后向"),
        ("ATS-5.3a-D2-02-S02-01", "第三方工具调用及服务端后向链路抓包", "第三方工具和服务端后向"),
        ("ATS-5.3a-D2-02-S02-02", "组件冷启动上报及服务端后向链路抓包", "组件冷启动上报和服务端后向"),
        ("ATS-5.3a-D2-02-S02-03", "崩溃上报及服务端后向链路抓包", "崩溃上报和服务端后向"),
        ("ATS-5.3a-D2-02-S02-04", "关键埋点上报及服务端后向链路抓包", "关键埋点上报和服务端后向"),
    )
}


class DownstreamPlaintextCaptureScenarioRunner(AgentTestCase):
    """Return not applicable without real channels and packet capture."""

    def run_downstream_plaintext_capture(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: DownstreamPlaintextCaptureVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须真实触发{variant.channel}链路，并同步取得客户端原始网络包、可读副本、"
                "服务端出口镜像及实际接收内容。当前 AgentModel 没有外部智能体、产品第三方上报"
                "组件、冷启动/崩溃/埋点入口、网络抓包或服务端后向镜像 Provider；本地 STDIO "
                "Mock Tool 不形成待测公网及服务端后向信道，不能替代本行真实链路"
            ),
        )
