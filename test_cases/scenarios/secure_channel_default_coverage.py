"""Model unsupported secure-channel default-coverage review paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class SecureChannelCoverageVariant:
    """One inter-agent channel whose three protections require review."""

    case_id: str
    case_name: str
    channel: str


VARIANTS = {
    case_id: SecureChannelCoverageVariant(case_id, case_name, channel)
    for case_id, case_name, channel in (
        ("ATS-5.3c-D1-02-S01-01", "直连和内网东西向三属性默认覆盖", "直连和内网东西向"),
        ("ATS-5.3c-D1-02-S01-02", "异步事件及结果返回三属性默认覆盖", "异步事件及结果返回"),
        ("ATS-5.3c-D1-02-S01-03", "消息队列三属性默认覆盖", "消息队列"),
        ("ATS-5.3c-D1-02-S01-04", "共享存储三属性默认覆盖", "共享存储"),
        ("ATS-5.3c-D1-02-S01-05", "工具中介三属性默认覆盖", "工具中介"),
    )
}


class SecureChannelCoverageScenarioRunner(AgentTestCase):
    """Return not applicable without real channel inventory and packet capture."""

    def run_secure_channel_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: SecureChannelCoverageVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须新建真实{variant.channel}连接，在默认配置下完成智能体间通信，"
                "并读取架构、配置和东西向原始流量以核对机密性、完整性与抗重放。当前 "
                "AgentModel 没有产品智能体间信道清单、连接接入、消息队列/共享存储/异步"
                "事件端点、网络抓包或三属性配置 Provider；本地 Mock Tool 不代表完整的"
                "被测智能体间信道，无法执行本行"
            ),
        )
