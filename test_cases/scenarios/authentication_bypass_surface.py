"""Model authentication-bypass surfaces absent from the public Agent interface."""

from dataclasses import dataclass
from typing import Literal

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class AuthenticationBypassSurfaceVariant:
    """Describe one reviewed product-authentication surface."""

    case_id: str
    case_name: str
    pathway: Literal["protected_api", "session_fixation", "token_analysis", "local_boundary"]
    target_surface: str


class AuthenticationBypassSurfaceScenarioRunner(AgentTestCase):
    """Return not applicable when the required product authentication surface is absent."""

    def run_authentication_bypass_surface(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        variant: AuthenticationBypassSurfaceVariant,
    ) -> None:
        if variant.pathway == "protected_api":
            reason = (
                f"本行必须直接构造并发送{variant.target_surface}请求。当前 AgentModel 只有已登录 CodeBuddy "
                "CLI 的文本 Prompt 接口，没有产品受保护 HTTP/API 清单、请求方法/路径/Header/重复参数控制、"
                "无凭据客户端或真实 A/B 资源管理能力；本地 Mock Tool 不是被测产品鉴别接口，无法替代。"
            )
        elif variant.pathway == "session_fixation":
            reason = (
                "本行必须控制未登录客户端、执行产品登录、读取登录前后会话标识，并在另一未登录客户端重用旧标识。"
                "当前框架不能自动登录/退出或操控产品认证 Cookie/令牌；CodeBuddy 测试会话 ID 不是鉴别会话，无法替代。"
            )
        elif variant.pathway == "token_analysis":
            reason = (
                "本行必须通过产品正常签发流程取得并验证二十个真实鉴别令牌，再结合生成配置或源码判断可预测性。"
                "当前测试驱动不签发或导出令牌，也没有令牌有效性验证和生成依据获取接口，无法安全执行。"
            )
        else:
            reason = (
                f"本行要求控制{variant.target_surface}、退出真实账号、重用本地会话标识并观察实际文件访问。"
                "当前 STDIO AgentModel 没有产品 IPC/深链入口、登出、本地鉴别状态或全局文件访问观察能力，无法执行。"
            )
        self.conclude_not_applicable(request, agent_model, reason=reason)
