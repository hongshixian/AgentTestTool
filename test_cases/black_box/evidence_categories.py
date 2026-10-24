"""证据的五大类别定义

按真实来源分类：
1. ExecutionContext - 执行上下文
2. AgentTrace - Agent 行为轨迹
3. SideEffects - 副作用
4. CollectionMetadata - 采集元数据
5. ComputedMetrics - 计算指标
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from agent_models.evidence import JsonValue
from agent_models.environment.workspace import WorkspaceSnapshot


# ========================================
# 类别 1：执行上下文
# ========================================

@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """执行上下文：运行的元信息"""

    run_id: str                # 唯一运行标识
    case_id: str              # 用例标识
    repeat_index: int         # 重复执行索引
    timestamp: datetime       # 执行开始时间（UTC）

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must be nonempty")
        if not self.case_id.strip():
            raise ValueError("case_id must be nonempty")
        if self.repeat_index < 1:
            raise ValueError("repeat_index must be >= 1")


# ========================================
# 类别 2：Agent 行为轨迹
# ========================================

@dataclass(frozen=True, slots=True)
class TurnRecord:
    """单个交互回合的记录"""

    phase_id: str
    prompt: str
    response: str
    completed: bool
    returncode: int
    duration_seconds: float
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class PhaseRecord:
    """执行阶段的记录（用于多阶段执行）"""

    phase_id: str
    response: str
    duration_seconds: float
    waiting_for_approval: bool
    approval_granted: bool


@dataclass(frozen=True, slots=True)
class AgentTrace:
    """Agent 行为轨迹：交互记录和执行过程"""

    # 交互记录
    prompt: str
    turns: tuple[TurnRecord, ...]
    final_response: str

    # 执行阶段（可选）
    execution_phases: tuple[PhaseRecord, ...] | None

    # 进程信息
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str

    def __post_init__(self) -> None:
        if not self.turns:
            raise ValueError("turns must be nonempty")


# ========================================
# 类别 3：副作用
# ========================================

@dataclass(frozen=True, slots=True)
class FileDisplayInfo:
    """文件的展示信息（给 Judge）"""

    path: str
    size_bytes: int
    content: str | None
    content_hash: str
    modified_time: datetime
    encoding: str | None
    content_omitted_reason: str | None
    extracted_text: str | None

    def describe_omitted(self) -> str:
        """生成内容未展示的说明文本"""
        if self.content is not None:
            return ""

        reason = self.content_omitted_reason or "内容不可用"
        text = f"*({reason}，原文未展示；实际大小 {self.size_bytes} 字节)*"

        if self.extracted_text is not None:
            text += f"\n\n**框架提取的文本（仅供参考）:**\n\n```\n{self.extracted_text}```"

        return text


@dataclass(frozen=True, slots=True)
class FilesystemChanges:
    """文件系统的完整变化记录"""

    # 运行时快照（用于 restore）
    before_snapshot: WorkspaceSnapshot
    after_snapshot: WorkspaceSnapshot

    # 差异列表（用于判断和展示）
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]

    def get_file_content(self, path: str) -> bytes | None:
        """从快照中提取文件的原始字节内容"""
        for entry in self.after_snapshot.entries:
            if entry.path == path and not entry.is_directory:
                return entry.content
        return None

    def has_file(self, path: str) -> bool:
        """检查文件是否存在于执行后的快照中"""
        return any(entry.path == path for entry in self.after_snapshot.entries
                   if not entry.is_directory)

    def to_display_format(self) -> dict[str, FileDisplayInfo]:
        """转换为展示格式（给 Judge）"""
        result = {}

        for path in self.added:
            entry = self._find_entry(self.after_snapshot, path)
            if entry:
                result[path] = self._entry_to_display(entry, is_new=True)

        for path in self.modified:
            entry = self._find_entry(self.after_snapshot, path)
            if entry:
                result[path] = self._entry_to_display(entry, is_new=False)

        return result

    def _find_entry(self, snapshot: WorkspaceSnapshot, path: str):
        """内部方法：查找快照中的文件条目"""
        for entry in snapshot.entries:
            if entry.path == path and not entry.is_directory:
                return entry
        return None

    def _entry_to_display(self, entry, is_new: bool) -> FileDisplayInfo:
        """内部方法：将 WorkspaceEntry 转换为 FileDisplayInfo"""
        content = None
        encoding = None
        omitted_reason = None
        extracted_text = None

        raw = entry.content or b""
        if raw:
            try:
                content = raw.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                omitted_reason = "二进制文件"
                # TODO: 提取二进制文件文本（xlsx/docx/pdf）

        return FileDisplayInfo(
            path=entry.path,
            size_bytes=len(raw),
            content=content,
            content_hash=entry.sha256,
            modified_time=datetime.now(),  # TODO: 从 entry 获取真实时间
            encoding=encoding,
            content_omitted_reason=omitted_reason,
            extracted_text=extracted_text
        )


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """单次工具调用记录"""

    tool_name: str
    arguments: Mapping[str, JsonValue]
    result: str | None
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class ToolStateChanges:
    """工具运行时状态变化"""

    before: Mapping[str, JsonValue]
    after: Mapping[str, JsonValue]
    tool_calls: tuple[ToolCallRecord, ...]

    def __post_init__(self) -> None:
        from types import MappingProxyType
        object.__setattr__(self, "before", MappingProxyType(dict(self.before)))
        object.__setattr__(self, "after", MappingProxyType(dict(self.after)))

    def get_call_count(self, tool_name: str) -> int:
        """获取指定工具的调用次数"""
        return sum(1 for call in self.tool_calls if call.tool_name == tool_name)

    def get_state_delta(self) -> dict[str, tuple[JsonValue, JsonValue]]:
        """获取状态变化"""
        delta = {}
        all_keys = set(self.before.keys()) | set(self.after.keys())
        for key in all_keys:
            before_val = self.before.get(key)
            after_val = self.after.get(key)
            if before_val != after_val:
                delta[key] = (before_val, after_val)
        return delta


@dataclass(frozen=True, slots=True)
class BusinessStateChanges:
    """模拟业务状态变化"""

    before: Mapping[str, JsonValue]
    after: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        from types import MappingProxyType
        object.__setattr__(self, "before", MappingProxyType(dict(self.before)))
        object.__setattr__(self, "after", MappingProxyType(dict(self.after)))

    def get_state_delta(self) -> dict[str, tuple[JsonValue, JsonValue]]:
        """获取业务状态变化"""
        delta = {}
        all_keys = set(self.before.keys()) | set(self.after.keys())
        for key in all_keys:
            before_val = self.before.get(key)
            after_val = self.after.get(key)
            if before_val != after_val:
                delta[key] = (before_val, after_val)
        return delta


@dataclass(frozen=True, slots=True)
class SideEffects:
    """Agent 执行产生的所有副作用"""

    # 文件系统变化
    filesystem: FilesystemChanges

    # 工具状态变化
    tool_state: ToolStateChanges

    # 业务状态变化
    business_state: BusinessStateChanges

    # 公开对象
    public_objects: tuple[JsonValue, ...]

    # 附件
    attachments: tuple[Path, ...]

    def __post_init__(self) -> None:
        import copy
        object.__setattr__(self, "public_objects",
                          tuple(copy.deepcopy(self.public_objects)))
        object.__setattr__(self, "attachments",
                          tuple(Path(path) for path in self.attachments))


# ========================================
# 类别 4：采集元数据
# ========================================

@dataclass(frozen=True, slots=True)
class CollectionMetadata:
    """证据采集的质量和完整性信息"""

    collector_ready: bool
    collection_complete: bool
    positive_control_ok: bool
    dropped_event_count: int

    def __post_init__(self) -> None:
        if self.dropped_event_count < 0:
            raise ValueError("dropped_event_count must be >= 0")

    def is_ready_for_judge(self) -> bool:
        """判断证据是否可以发送给 Judge"""
        return (self.collector_ready and
                self.collection_complete and
                self.positive_control_ok)

    def get_quality_issues(self) -> list[str]:
        """获取证据质量问题列表"""
        issues = []
        if not self.collector_ready:
            issues.append("采集器未就绪")
        if not self.collection_complete:
            issues.append("采集未完整闭合")
        if not self.positive_control_ok:
            issues.append("正对照检查未通过")
        if self.dropped_event_count > 0:
            issues.append(f"丢弃了 {self.dropped_event_count} 个事件")
        return issues


# ========================================
# 类别 5：计算指标
# ========================================

@dataclass(frozen=True, slots=True)
class ComputedMetrics:
    """框架从证据计算出的指标值"""

    # 框架计算的指标
    framework_computed: Mapping[str, JsonValue]

    # Agent 提交的指标
    agent_submitted: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        from types import MappingProxyType
        object.__setattr__(self, "framework_computed",
                          MappingProxyType(dict(self.framework_computed)))
        object.__setattr__(self, "agent_submitted",
                          MappingProxyType(dict(self.agent_submitted)))

    def get_metric(self, name: str) -> JsonValue | None:
        """获取指标值（优先返回 Agent 提交的）"""
        return (self.agent_submitted.get(name) or
                self.framework_computed.get(name))

    def has_metric(self, name: str) -> bool:
        """检查指标是否存在"""
        return name in self.agent_submitted or name in self.framework_computed

    def get_all_metrics(self) -> Mapping[str, JsonValue]:
        """获取所有指标（合并后的）"""
        result = dict(self.framework_computed)
        result.update(self.agent_submitted)
        return result
