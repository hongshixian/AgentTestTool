"""统一的黑盒证据容器

设计原则：
1. 按真实来源分类（5 大类）
2. 内部字段私有（`_` 前缀）
3. 对外暴露 41 个公开方法
4. 消费者通过方法访问，不直接访问字段
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from agent_models.evidence import JsonValue
from test_cases.black_box.evidence_categories import (
    AgentTrace,
    CollectionMetadata,
    ComputedMetrics,
    ExecutionContext,
    FileDisplayInfo,
    SideEffects,
)


@dataclass(frozen=True, slots=True)
class TurnInfo:
    """简化的回合信息（给消费者）"""
    phase_id: str
    completed: bool
    returncode: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class UnifiedEvidence:
    """统一的黑盒证据容器

    设计原则：
    1. 按真实来源分类（5 大类）
    2. 每一类有合理的嵌套深度（不超过 3 层）
    3. 对外暴露方法，隐藏内部结构
    4. 消费者通过方法访问，不直接访问字段
    """

    # === 内部结构（私有，消费者不可见）===

    # 第一类：执行上下文
    _context: ExecutionContext

    # 第二类：Agent 行为轨迹
    _trace: AgentTrace

    # 第三类：副作用（嵌套 2 层）
    _side_effects: SideEffects

    # 第四类：采集元数据
    _collection: CollectionMetadata

    # 第五类：计算指标
    _metrics: ComputedMetrics

    # ========================================
    # 对外接口：消费者只调用这些方法
    # ========================================

    # --- 1. 状态查询接口 ---

    def is_ready_for_judge(self) -> bool:
        """判断证据是否可以发送给 Judge"""
        return self._collection.is_ready_for_judge()

    def get_quality_issues(self) -> list[str]:
        """获取证据质量问题列表"""
        return self._collection.get_quality_issues()

    def is_successful(self) -> bool:
        """判断进程是否成功退出"""
        return self._trace.exit_code == 0

    def has_errors(self) -> bool:
        """判断是否有标准错误输出"""
        return bool(self._trace.stderr and self._trace.stderr.strip())

    def has_file(self, path: str) -> bool:
        """检查文件是否存在"""
        return self._side_effects.filesystem.has_file(path)

    def is_file_modified(self, path: str) -> bool:
        """检查文件是否被修改"""
        return (path in self._side_effects.filesystem.modified or
                path in self._side_effects.filesystem.deleted)

    def is_file_deleted(self, path: str) -> bool:
        """检查文件是否被删除"""
        return path in self._side_effects.filesystem.deleted

    # --- 2. 数据访问接口 ---

    # 2.1 基本信息
    def get_case_id(self) -> str:
        """获取用例标识"""
        return self._context.case_id

    def get_run_id(self) -> str:
        """获取运行标识"""
        return self._context.run_id

    def get_repeat_index(self) -> int:
        """获取重复执行索引"""
        return self._context.repeat_index

    # 2.2 交互数据
    def get_prompt(self) -> str:
        """获取用户输入的 prompt"""
        return self._trace.prompt

    def get_agent_response(self) -> str:
        """获取 Agent 的最终响应"""
        return self._trace.final_response

    def get_all_turns(self) -> tuple[TurnInfo, ...]:
        """获取所有交互回合的信息"""
        return tuple(
            TurnInfo(
                phase_id=turn.phase_id,
                completed=turn.completed,
                returncode=turn.returncode,
                duration_seconds=turn.duration_seconds
            )
            for turn in self._trace.turns
        )

    def get_execution_time(self) -> float:
        """获取总执行时长"""
        return self._trace.duration_seconds

    # 2.3 文件数据
    def get_file_content(self, path: str) -> str | None:
        """获取文件的文本内容"""
        raw = self._side_effects.filesystem.get_file_content(path)
        if raw is None:
            return None
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return None

    def get_files_added(self) -> tuple[str, ...]:
        """获取新增文件的路径列表"""
        return self._side_effects.filesystem.added

    def get_files_modified(self) -> tuple[str, ...]:
        """获取修改文件的路径列表"""
        return self._side_effects.filesystem.modified

    def get_files_deleted(self) -> tuple[str, ...]:
        """获取删除文件的路径列表"""
        return self._side_effects.filesystem.deleted

    def get_file_changes_summary(self) -> dict[str, int]:
        """获取文件变化统计"""
        return {
            "added": len(self._side_effects.filesystem.added),
            "modified": len(self._side_effects.filesystem.modified),
            "deleted": len(self._side_effects.filesystem.deleted),
            "total_changes": (len(self._side_effects.filesystem.added) +
                             len(self._side_effects.filesystem.modified) +
                             len(self._side_effects.filesystem.deleted))
        }

    # 2.4 指标数据
    def get_metric(self, name: str) -> JsonValue | None:
        """获取指标值"""
        return self._metrics.get_metric(name)

    def has_metric(self, name: str) -> bool:
        """检查指标是否存在"""
        return self._metrics.has_metric(name)

    def get_all_metrics(self) -> Mapping[str, JsonValue]:
        """获取所有指标"""
        return self._metrics.get_all_metrics()

    # 2.5 工具调用数据
    def get_tool_call_count(self, tool_name: str | None = None) -> int:
        """获取工具调用次数"""
        if tool_name is None:
            return len(self._side_effects.tool_state.tool_calls)
        return self._side_effects.tool_state.get_call_count(tool_name)

    # --- 3. 转换导出接口 ---

    def to_judge_prompt(self) -> str:
        """为 Judge 生成完整的证据文本"""
        sections = []

        # 1. 上下文
        sections.append(f"## 测试上下文\n")
        sections.append(f"- 用例 ID: {self._context.case_id}\n")
        sections.append(f"- 运行 ID: {self._context.run_id}\n")
        sections.append(f"- 执行时间: {self._trace.duration_seconds:.2f} 秒\n\n")

        # 2. 用户交互
        sections.append(f"## 用户 Prompt\n\n{self._trace.prompt}\n\n")
        sections.append(self._format_agent_trace())

        # 3. 文件变化
        sections.append(self._format_filesystem_changes())

        # 4. 指标
        if self._metrics.framework_computed or self._metrics.agent_submitted:
            sections.append(self._format_metrics())

        return "".join(sections)

    def to_summary_dict(self) -> dict:
        """返回脱敏的、可序列化的摘要"""
        return {
            "run_id": self._context.run_id,
            "case_id": self._context.case_id,
            "timestamp": self._context.timestamp.isoformat(),
            "execution_time_seconds": self._trace.duration_seconds,
            "exit_code": self._trace.exit_code,
            "collection_ready": self._collection.collector_ready,
            "collection_complete": self._collection.collection_complete,
            "positive_control_ok": self._collection.positive_control_ok,
            "files_added": list(self._side_effects.filesystem.added),
            "files_modified": list(self._side_effects.filesystem.modified),
            "files_deleted": list(self._side_effects.filesystem.deleted),
            "metrics": dict(self._metrics.get_all_metrics()),
        }

    # --- 内部方法（私有）---

    def _format_agent_trace(self) -> str:
        """格式化 Agent 行为轨迹"""
        if self._trace.execution_phases:
            # 多阶段执行
            result = f"## Agent 执行流程\n\n"
            result += f"Agent 按照 {len(self._trace.execution_phases)} 个阶段执行任务：\n\n"
            for i, phase in enumerate(self._trace.execution_phases, 1):
                result += f"### 阶段 {i}: {phase.phase_id}\n\n"
                result += f"```\n{phase.response}\n```\n\n"
                result += f"- 耗时: {phase.duration_seconds:.2f} 秒\n\n"
            return result
        else:
            # 单阶段执行
            return f"## Agent 响应\n\n{self._trace.final_response}\n\n"

    def _format_filesystem_changes(self) -> str:
        """格式化文件系统变化"""
        result = f"## 工作区变化\n\n"
        result += f"- 新增文件: {len(self._side_effects.filesystem.added)} 个\n"
        result += f"- 修改文件: {len(self._side_effects.filesystem.modified)} 个\n"
        result += f"- 删除文件: {len(self._side_effects.filesystem.deleted)} 个\n\n"

        # 展示新增文件内容
        display_format = self._side_effects.filesystem.to_display_format()
        for path in self._side_effects.filesystem.added:
            info = display_format.get(path)
            if info:
                result += f"### 文件: {path}\n\n"
                result += f"- 大小: {info.size_bytes} 字节\n\n"
                if info.content is not None:
                    result += f"**内容:**\n\n```\n{info.content}\n```\n\n"
                else:
                    result += f"{info.describe_omitted()}\n\n"

        # 展示修改文件
        for path in self._side_effects.filesystem.modified:
            info = display_format.get(path)
            if info:
                result += f"### 文件: {path}\n\n"
                result += f"- 大小: {info.size_bytes} 字节\n\n"
                if info.content is not None:
                    result += f"**修改后内容:**\n\n```\n{info.content}\n```\n\n"
                else:
                    result += f"{info.describe_omitted()}\n\n"

        return result

    def _format_metrics(self) -> str:
        """格式化指标"""
        result = f"## 指标\n\n"

        if self._metrics.framework_computed:
            result += "### 框架计算的指标\n\n"
            for name, value in self._metrics.framework_computed.items():
                result += f"- {name}: {value}\n"
            result += "\n"

        if self._metrics.agent_submitted:
            result += "### Agent 提交的指标\n\n"
            for name, value in self._metrics.agent_submitted.items():
                result += f"- {name}: {value}\n"
            result += "\n"

        return result
