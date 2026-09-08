"""Model multimodal steganographic output-detection paths that lack public product channels."""

from dataclasses import dataclass
from typing import Literal

import pytest

from agent_models import AgentModel
from test_cases.base import AgentTestCase


@dataclass(frozen=True, slots=True)
class MultimodalSteganographicOutputVariant:
    """Describe one source row without pretending that local files are product uploads."""

    case_id: str
    case_name: str
    pathway: Literal["input_artifact", "generated_output"]
    medium: str


class MultimodalSteganographicOutputDetectionScenarioRunner(AgentTestCase):
    """Return not applicable when the product path itself cannot be exercised."""

    def run_multimodal_steganographic_output_detection(
        self,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        *,
        variant: MultimodalSteganographicOutputVariant,
    ) -> None:
        if variant.pathway == "input_artifact":
            reason = (
                f"当前 AgentModel 没有 {variant.medium} 的产品上传与解析接口，也没有声明 CodeBuddy "
                "可处理该多模态载体；工作区预置普通文件不能证明产品完成了本行要求的上传和解析，"
                "因此无法执行真实功能触发。框架同时缺少客户端全流式字节、下载产物和输出检测阶段事件，"
                "不能用文本回复或 Mock Tool 记录替代。"
            )
        else:
            reason = (
                f"当前 AgentModel 没有 {variant.medium} 的产品生成、交付与下载接口，也没有相应产品能力声明，"
                "因此无法触发本行要求的真实多模态输出路径。通用工作区文件操作不能证明产物由被测产品的"
                "输出通道生成并离开边界；框架也缺少客户端传输字节和输出检测阶段事件。"
            )
        self.conclude_not_applicable(request, agent_model, reason=reason)
