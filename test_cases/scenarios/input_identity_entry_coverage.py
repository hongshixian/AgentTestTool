"""Model unsupported product input-identity entry coverage paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class InputIdentityEntryVariant:
    """One product input entry requiring input-party identification."""

    case_id: str
    case_name: str
    entry: str


VARIANTS = {
    case_id: InputIdentityEntryVariant(case_id, case_name, entry)
    for case_id, case_name, entry in (
        ("ATS-6.1a-D1-02-S01-01", "用户 UI/API 登录纳入识别及方式交集", "用户 UI 或 API 登录"),
        ("ATS-6.1a-D1-02-S01-02", "开放 API纳入识别及方式交集", "开放 API"),
        ("ATS-6.1a-D1-02-S01-03", "其他智能体协议调用纳入识别及方式交集", "其他智能体协议调用"),
        ("ATS-6.1a-D1-02-S01-04", "工具或服务返回入口纳入识别及方式交集", "工具或服务结果返回"),
        ("ATS-6.1a-D1-02-S01-05", "Webhook纳入识别及方式交集", "Webhook 事件"),
        ("ATS-6.1a-D1-02-S01-06", "上游编排或内部服务纳入识别及方式交集", "上游编排或内部服务"),
        ("ATS-6.1a-D1-02-S01-07", "定时触发纳入识别及方式交集", "定时任务触发"),
        ("ATS-6.1a-D1-02-S01-08", "终端本地输入纳入识别及方式交集", "终端本地输入"),
    )
}


class InputIdentityEntryScenarioRunner(AgentTestCase):
    """Return not applicable without product entry and identity control planes."""

    def run_input_identity_entry_coverage(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: InputIdentityEntryVariant,
    ) -> None:
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=(
                f"本行必须先从产品路由、注册、订阅和部署配置确认“{variant.entry}”真实入口，再以绑定主体凭据"
                "完成正常输入并读取识别策略、双方支持方式交集、接入记录和真实凭据持有者。当前 CodeBuddy"
                "适配只暴露一个 CLI prompt 通道，不能枚举产品全部入口或读取权威用户/实例身份、识别策略和"
                "接入日志；Mock Tool 返回不具备产品认可的服务主体凭据，因而不能替代目标入口验证"
            ),
        )
