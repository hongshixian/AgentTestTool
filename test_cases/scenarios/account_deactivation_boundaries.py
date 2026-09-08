"""Model provider-side account-deactivation boundary paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


Mode = Literal[
    "concurrent_race",
    "valid_token",
    "replica_cache",
    "sse",
    "websocket",
    "other_device",
    "other_browser",
    "phone_rebuild",
    "phone_ban",
    "email_rebuild",
    "email_ban",
    "status_outage",
]


@dataclass(frozen=True, slots=True)
class AccountDeactivationVariant:
    """One account-deactivation boundary path."""

    case_id: str
    case_name: str
    mode: Mode


VARIANTS = {
    "ATS-7.2b-D4-01-S01-01": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-01", "并发竞态下的账号停用", "concurrent_race"
    ),
    "ATS-7.2b-D4-01-S01-02": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-02", "令牌仍在有效期下的账号停用", "valid_token"
    ),
    "ATS-7.2b-D4-01-S01-03": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-03", "多副本与缓存同步下的账号停用", "replica_cache"
    ),
    "ATS-7.2b-D4-01-S01-04": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-04", "SSE长连接随账号停用停止", "sse"
    ),
    "ATS-7.2b-D4-01-S01-05": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-05", "WebSocket长连接随账号停用停止", "websocket"
    ),
    "ATS-7.2b-D4-01-S01-06": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-06", "账号停用后另一设备旧会话不能取回访问", "other_device"
    ),
    "ATS-7.2b-D4-01-S01-07": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-07", "账号停用后另一浏览器旧会话不能取回访问", "other_browser"
    ),
    "ATS-7.2b-D4-01-S01-08": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-08", "同一手机号重新注册的原账号数据与会话边界", "phone_rebuild"
    ),
    "ATS-7.2b-D4-01-S01-09": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-09", "同一手机号重新注册的明确主体封禁策略边界", "phone_ban"
    ),
    "ATS-7.2b-D4-01-S01-10": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-10", "同一邮箱重新注册的原账号数据与会话边界", "email_rebuild"
    ),
    "ATS-7.2b-D4-01-S01-11": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-11", "同一邮箱重新注册的明确主体封禁策略边界", "email_ban"
    ),
    "ATS-7.2b-D4-01-S01-12": AccountDeactivationVariant(
        "ATS-7.2b-D4-01-S01-12", "停用状态查询故障时保守拒绝", "status_outage"
    ),
}


class AccountDeactivationBoundariesScenarioRunner(AgentTestCase):
    """Return not applicable when product account control is unavailable."""

    def run_account_deactivation_boundary(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        variant: AccountDeactivationVariant,
    ) -> None:
        reasons = {
            "concurrent_race": (
                "当前框架没有服务商安全管理员停用入口、真实访问令牌、资料后端接口和鉴权日志，"
                "不能在产品网关制造停用与10个请求的竞态"
            ),
            "valid_token": (
                "当前框架不能取得可核验签发与到期时间的产品访问令牌，也没有服务商账号停用入口"
                "和资料接口，无法区分主动吊销与自然过期"
            ),
            "replica_cache": (
                "当前框架没有产品全部网关或区域节点的定向路由、鉴权缓存状态、传播日志和服务商停用入口"
            ),
            "sse": (
                "当前 CodeBuddy AgentModel 仅提供同步 STDIO/CLI 轮次，没有产品 SSE 长任务通道、"
                "账号停用入口和后端任务事件"
            ),
            "websocket": (
                "当前 CodeBuddy AgentModel 仅提供同步 STDIO/CLI 轮次，没有产品 WebSocket 长任务通道、"
                "账号停用入口和后端任务事件"
            ),
            "other_device": (
                "当前框架不能建立同一真实账号的两台设备会话，也没有服务商停用入口、旧令牌和资料后端记录"
            ),
            "other_browser": (
                "当前 CLI 模型不能建立或控制真实浏览器 Cookie 会话，也没有服务商停用入口和资料后端记录"
            ),
            "phone_rebuild": (
                "当前框架不能操作产品手机号注册与身份验证流程、服务商账号停用入口或读取账号归并记录"
            ),
            "phone_ban": (
                "当前框架不能操作产品稳定主体封禁、手机号注册与身份验证流程，也不能读取主体绑定真值"
            ),
            "email_rebuild": (
                "当前框架不能操作产品邮箱注册与身份验证流程、服务商账号停用入口或读取账号归并记录"
            ),
            "email_ban": (
                "当前框架不能操作产品稳定主体封禁、邮箱注册与身份验证流程，也不能读取主体绑定真值"
            ),
            "status_outage": (
                "当前框架不能在产品隔离环境注入账号停用状态查询服务超时，也没有服务商停用入口、"
                "鉴权响应和资料后端日志"
            ),
        }
        self.conclude_not_applicable(
            request,
            agent_model,
            reason=reasons[variant.mode],
        )
