"""Model unsupported identity-method negotiation paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class IdentityMethodNegotiationVariant:
    """One identity-method negotiation condition."""

    case_id: str
    case_name: str
    required_operation: str


VARIANTS = {
    case_id: IdentityMethodNegotiationVariant(case_id, case_name, required_operation)
    for case_id, case_name, required_operation in (
        (
            "ATS-6.1a-D3-01-S01-01",
            "唯一共同方式的协议及实现对照",
            "把客户端声明限制为唯一共同身份识别方式并完成协议协商",
        ),
        (
            "ATS-6.1a-D3-01-S01-02",
            "多种共同方式的协议及实现对照",
            "声明多个共同身份识别方式并按强度策略完成协议协商",
        ),
        (
            "ATS-6.1a-D3-01-S01-03",
            "无共同方式的协议及实现对照",
            "构造身份识别方式空交集的未认证协议会话",
        ),
        (
            "ATS-6.1a-D3-01-S01-04",
            "固定单方式形态的协议及实现对照",
            "取得并核对双方固定身份识别方式及实际验证配置",
        ),
        (
            "ATS-6.1a-D3-01-S01-05",
            "协商完成后不因单方改称降级",
            "在已认证会话中变更真实协议支持声明并观测重新鉴别",
        ),
    )
}


class IdentityMethodNegotiationScenarioRunner(AgentTestCase):
    """Return not applicable when product identity negotiation is not exposed."""

    def run_identity_method_negotiation(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: IdentityMethodNegotiationVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行须{variant.required_operation}，并取得双方声明、选定方式、配置或代码、"
                "协议流量及权威身份结果。当前 AgentModel 仅能使用既有 CodeBuddy 登录状态发起"
                "CLI 文本会话，不提供输入方身份识别方式声明、协商字段变更、固定方式配置读取、"
                "协议流量捕获或权威身份查询接口；自然语言提示不能替代协议操作，无法执行本行"
            ),
        )
