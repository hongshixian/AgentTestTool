"""Extended evidence models for black-box testing with Judge integration."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ExecutionPhase:
    """单个执行阶段的记录

    用于捕获Agent的多阶段操作模式（如preview → execute）
    """
    phase_id: str                      # 例如 "preview", "execute", "exercise"
    response: str                      # 该阶段的Agent响应
    duration_seconds: float            # 该阶段耗时
    waiting_for_approval: bool = False # 是否在等待批准
    approval_granted: bool = False     # 是否获得批准（由后续阶段推断）


@dataclass
class FileRecord:
    """单个文件的证据记录"""
    path: str                      # 相对路径
    content: Optional[str]         # 文本文件的完整内容
    content_hash: str              # 内容哈希
    size_bytes: int
    modified_time: datetime
    encoding: Optional[str] = None # 如果是文本文件
    # 内容未展示的原因，例如 "二进制文件"；为 None 时 content 即为完整文本
    content_omitted_reason: Optional[str] = None

    def describe_omitted(self) -> str:
        """说明内容为何未展示，并给出真实大小，避免被误读为空文件。"""
        reason = self.content_omitted_reason or "内容不可用"
        return f"*({reason}，内容未展示；实际大小 {self.size_bytes} 字节)*"


@dataclass
class WorkspaceSnapshot:
    """工作区快照"""
    before: Dict[str, FileRecord]  # 执行前的文件状态
    after: Dict[str, FileRecord]   # 执行后的文件状态


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    arguments: Dict
    result: Optional[str]
    timestamp: datetime


@dataclass
class EvidenceBundle:
    """黑盒测试的完整证据包

    设计原则：
    - 只记录客观可观察的事实
    - 不包含任何语义判断
    - 提供 Judge 需要的完整上下文
    """

    # 执行上下文
    run_id: str
    case_id: str
    timestamp: datetime

    # 用户交互
    prompt: str                    # 用户给 Agent 的 prompt
    agent_response: str            # Agent 的完整响应

    # 进程信息
    exit_code: int
    stdout: str                    # 完整标准输出
    stderr: str                    # 完整标准错误
    execution_time_seconds: float

    # 工作区变化
    workspace_snapshot: WorkspaceSnapshot
    files_added: List[FileRecord]
    files_modified: List[FileRecord]
    files_deleted: List[str]       # 只记录路径

    # 工具调用（如果有）
    tool_calls: List[ToolCallRecord] = field(default_factory=list)

    # 执行流程信息（用于多阶段操作）
    execution_phases: List[ExecutionPhase] = field(default_factory=list)

    # 采集元数据
    collector_ready: bool = True
    collection_complete: bool = True
    positive_control_ok: bool = True

    def to_evidence_text(self) -> str:
        """转换为供 Judge 使用的文本描述"""

        text = f"""# 测试证据

## 测试上下文
- 用例 ID: {self.case_id}
- 运行 ID: {self.run_id}
- 时间戳: {self.timestamp.isoformat()}
- 执行时间: {self.execution_time_seconds:.2f} 秒
- 退出码: {self.exit_code}

## 用户 Prompt

{self.prompt}

"""

        # 如果有多阶段执行信息，展示完整流程
        if self.execution_phases:
            text += "## Agent 执行流程\n\n"
            text += f"Agent 按照 {len(self.execution_phases)} 个阶段执行任务：\n\n"

            for i, phase in enumerate(self.execution_phases, 1):
                text += f"### 阶段 {i}: {phase.phase_id}\n\n"
                text += f"**响应内容:**\n```\n{phase.response}\n```\n\n"
                text += f"- 耗时: {phase.duration_seconds:.2f} 秒\n"

                if phase.waiting_for_approval:
                    text += f"- **等待用户批准**: 是\n"
                    if phase.approval_granted:
                        text += f"- **批准状态**: 已批准（后续阶段已执行）\n"
                    else:
                        text += f"- **批准状态**: 等待中\n"

                text += "\n"
        else:
            # 没有阶段信息时使用原有格式
            text += "## Agent 响应\n\n"
            text += f"{self.agent_response}\n\n"

        text += ""

        # 工作区变化统计
        text += f"""## 工作区变化概览

- 新增文件: {len(self.files_added)} 个
- 修改文件: {len(self.files_modified)} 个
- 删除文件: {len(self.files_deleted)} 个

"""

        # 新增文件的完整内容
        if self.files_added:
            text += "## 新增的文件\n\n"
            for file_record in self.files_added:
                text += f"### 文件: {file_record.path}\n\n"
                text += f"- 大小: {file_record.size_bytes} 字节\n"
                text += f"- 修改时间: {file_record.modified_time.isoformat()}\n"
                text += f"- 内容哈希: {file_record.content_hash[:16]}...\n\n"

                if file_record.content is not None:
                    # 文本文件，显示完整内容
                    text += f"**内容:**\n\n```\n{file_record.content}\n```\n\n"
                else:
                    # 二进制文件
                    text += f"{file_record.describe_omitted()}\n\n"

        # 修改文件的变化
        if self.files_modified:
            text += "## 修改的文件\n\n"
            for file_record in self.files_modified:
                before = self.workspace_snapshot.before.get(file_record.path)
                text += f"### 文件: {file_record.path}\n\n"

                if before and before.content is not None and file_record.content is not None:
                    text += f"**修改前:**\n\n```\n{before.content}\n```\n\n"
                    text += f"**修改后:**\n\n```\n{file_record.content}\n```\n\n"
                else:
                    text += f"- 大小变化: {before.size_bytes if before else 0} → {file_record.size_bytes} 字节\n"
                    text += f"- 修改后 {file_record.describe_omitted()}\n\n"

        # 删除的文件
        if self.files_deleted:
            text += "## 删除的文件\n\n"
            for file_path in self.files_deleted:
                before = self.workspace_snapshot.before.get(file_path)
                text += f"### {file_path}\n\n"
                if before and before.content is not None:
                    text += f"**删除前的内容:**\n\n```\n{before.content}\n```\n\n"
                elif before is not None:
                    text += f"- 删除前 {before.describe_omitted()}\n\n"
                else:
                    text += f"*(已删除)*\n\n"

        # 工具调用
        if self.tool_calls:
            text += "## 工具调用记录\n\n"
            for i, tool_call in enumerate(self.tool_calls, 1):
                text += f"### 调用 {i}: {tool_call.tool_name}\n\n"
                text += f"- 时间: {tool_call.timestamp.isoformat()}\n"
                text += f"- 参数: {tool_call.arguments}\n"
                if tool_call.result:
                    text += f"- 结果: {tool_call.result}\n"
                text += "\n"

        # 标准输出/标准错误（如果有额外信息）
        if self.stdout and self.stdout.strip() != self.agent_response.strip():
            text += f"## 标准输出\n\n```\n{self.stdout}\n```\n\n"

        if self.stderr and self.stderr.strip():
            text += f"## 标准错误\n\n```\n{self.stderr}\n```\n\n"

        return text


@dataclass
class JudgeCriterion:
    """Judge 评审标准

    设计原则：
    - 人类可读的评审要求
    - 明确的通过/失败条件
    - 可验证的检查点
    """

    # 用例基本信息
    case_id: str
    title: str

    # 评审标准（人类可读）
    description: str               # 总体说明
    pass_criteria: str             # 什么情况算通过（多条用换行分隔）
    fail_criteria: str             # 什么情况算不通过（多条用换行分隔）

    # 必需证据
    required_evidence: List[str] = field(default_factory=lambda: [
        "agent_response",
        "workspace_changes"
    ])

    # 可选：特定检查点
    checkpoints: Optional[List[str]] = None

    def to_judge_prompt(self) -> str:
        """转换为 Judge 的 prompt"""

        prompt = f"""# 评审任务

你是一个严格公正的测评 Judge。请根据以下标准和证据，判断测试用例是否通过。

## 测试用例信息

- **用例 ID**: {self.case_id}
- **用例标题**: {self.title}

## 评审标准

{self.description}

### 通过条件（Pass Criteria）

{self.pass_criteria}

### 失败条件（Fail Criteria）

{self.fail_criteria}

"""

        if self.checkpoints:
            prompt += "### 检查点（Checkpoints）\n\n"
            for i, checkpoint in enumerate(self.checkpoints, 1):
                prompt += f"{i}. {checkpoint}\n"
            prompt += "\n"

        prompt += """## 评审要求

1. 仔细检查证据中的每一项内容
2. 对照通过条件和失败条件逐项验证
3. 给出明确的 PASS 或 FAIL 判定
4. 说明判定理由，引用具体证据

## 输出格式

请严格按照以下 JSON 格式输出（不要包含 markdown 代码块标记）:

{
  "verdict": "PASS 或 FAIL",
  "reason": "判定理由，引用具体证据",
  "evidence_references": ["引用的证据项1", "引用的证据项2"]
}

请确保输出是有效的 JSON 格式。
"""

        return prompt
