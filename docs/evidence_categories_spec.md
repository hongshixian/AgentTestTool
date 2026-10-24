# 黑盒证据容器类别定义规范

**版本**: v1.0  
**日期**: 2026-10-24  
**状态**: 草案（Draft）

## 概述

本文档定义统一证据容器 `UnifiedEvidence` 的内部数据结构。证据按**真实来源和语义**组织为 5 大类别，每类有合理的嵌套深度（不超过 3 层）。

## 设计原则

1. **语义驱动**：按证据的真实来源分类，而非机械地扁平或嵌套
2. **嵌套有度**：最深 3 层，符合人的认知
3. **职责清晰**：每个类别负责一类证据的采集、存储和转换
4. **扩展友好**：新增证据类型在对应类别下扩展
5. **信息隐藏**：内部结构对消费者不可见，只通过方法访问

---

## 类别 1：执行上下文（Execution Context）

### 语义
标识这次运行本身的元信息：**"谁在什么时候跑了什么用例"**

### 结构定义

```python
@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """执行上下文：运行的元信息"""
    
    run_id: str                # 唯一运行标识（UUID）
    case_id: str              # 用例标识（如 "B001", "T053"）
    repeat_index: int         # 重复执行索引（从 1 开始）
    timestamp: datetime       # 执行开始时间（UTC）
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `run_id` | `str` | 全局唯一的运行标识，用于关联日志和工件 | `"run_20261024_153042_a3f8"` |
| `case_id` | `str` | 用例 ID，全局唯一，不透明字符串 | `"B001"`, `"T053"` |
| `repeat_index` | `int` | 重复执行的索引（spec.repeat_count > 1 时使用） | `1`, `2`, `3` |
| `timestamp` | `datetime` | 执行开始时刻，UTC 时区 | `datetime(2026, 10, 24, 15, 30, 42)` |

### 职责边界

- ✅ 只包含运行标识信息
- ❌ 不包含执行结果或进程信息（属于 AgentTrace）
- ❌ 不包含用例规格（由 spec 提供）

---

## 类别 2：Agent 行为轨迹（Agent Trace）

### 语义
Agent 的交互记录和执行过程：**"Agent 做了什么"**

### 结构定义

```python
@dataclass(frozen=True, slots=True)
class AgentTrace:
    """Agent 行为轨迹：交互记录和执行过程"""
    
    # 交互记录
    prompt: str                              # 用户输入（首个 step 的 prompt）
    turns: tuple[TurnRecord, ...]            # 多回合记录
    final_response: str                      # 最终响应（所有 turn 的合并）
    
    # 执行阶段（可选，用于多阶段执行模式）
    execution_phases: tuple[PhaseRecord, ...] | None
    
    # 进程信息
    exit_code: int                           # 进程退出码
    duration_seconds: float                  # 总执行时长
    stdout: str                              # 标准输出
    stderr: str                              # 标准错误
```

### 子类型定义

#### TurnRecord

```python
@dataclass(frozen=True, slots=True)
class TurnRecord:
    """单个交互回合的记录"""
    
    phase_id: str              # 阶段标识（如 "exercise", "preview"）
    prompt: str                # 该回合的输入
    response: str              # Agent 的响应
    completed: bool            # Agent 是否完成任务
    returncode: int            # 该回合的退出码
    duration_seconds: float    # 该回合耗时
    session_id: str | None     # 会话标识（如有）
```

#### PhaseRecord

```python
@dataclass(frozen=True, slots=True)
class PhaseRecord:
    """执行阶段的记录（用于多阶段执行模式）"""
    
    phase_id: str                  # 阶段标识
    response: str                  # 该阶段的响应
    duration_seconds: float        # 该阶段耗时
    waiting_for_approval: bool     # 是否在等待批准
    approval_granted: bool         # 是否已获得批准
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str` | 用户给 Agent 的首个 prompt，通常来自 `spec.steps[0].prompt` |
| `turns` | `tuple[TurnRecord, ...]` | 多回合记录，每个 turn 对应一次交互 |
| `final_response` | `str` | 所有 turn 的 response 合并，用于 Judge 展示 |
| `execution_phases` | `tuple[PhaseRecord, ...] \| None` | 多阶段执行时（如 preview → execute）的详细记录 |
| `exit_code` | `int` | 最终的进程退出码（0 表示成功） |
| `duration_seconds` | `float` | 从开始到结束的总耗时 |
| `stdout` | `str` | 完整的标准输出（如有） |
| `stderr` | `str` | 完整的标准错误（如有） |

### 职责边界

- ✅ 包含 Agent 的所有交互行为和进程信息
- ✅ 包含多阶段执行的详细记录
- ❌ 不包含副作用（文件变化、工具调用等属于 SideEffects）
- ❌ 不包含采集质量信息（属于 CollectionMetadata）

---

## 类别 3：副作用（Side Effects）

### 语义
Agent 执行产生的外部可观察变化：**"Agent 改变了什么"**

### 结构定义

```python
@dataclass(frozen=True, slots=True)
class SideEffects:
    """Agent 执行产生的所有副作用"""
    
    # 3.1 文件系统变化
    filesystem: FilesystemChanges
    
    # 3.2 工具状态变化
    tool_state: ToolStateChanges
    
    # 3.3 业务状态变化（模拟）
    business_state: BusinessStateChanges
    
    # 3.4 公开对象（某些用例会提交结构化对象）
    public_objects: tuple[JsonValue, ...]
    
    # 3.5 附件（某些用例会生成附件）
    attachments: tuple[Path, ...]
```

### 3.1 FilesystemChanges

```python
@dataclass(frozen=True, slots=True)
class FilesystemChanges:
    """文件系统的完整变化记录"""
    
    # 运行时快照（用于 restore，来自 agent_models.environment.workspace）
    before_snapshot: WorkspaceSnapshot
    after_snapshot: WorkspaceSnapshot
    
    # 差异列表（用于判断和展示）
    added: tuple[str, ...]       # 新增文件的路径列表
    modified: tuple[str, ...]    # 修改文件的路径列表
    deleted: tuple[str, ...]     # 删除文件的路径列表
    
    # === 对外方法（消费者调用这些方法，不直接访问字段）===
    
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
        """转换为展示格式（给 Judge）
        
        Returns:
            字典，key 为文件路径，value 为 FileDisplayInfo
        """
        pass  # 实现见下文
```

#### FileDisplayInfo

```python
@dataclass(frozen=True, slots=True)
class FileDisplayInfo:
    """文件的展示信息（给 Judge）"""
    
    path: str                          # 文件路径
    size_bytes: int                    # 文件大小
    content: str | None                # 文本内容（UTF-8 可解码）
    content_hash: str                  # SHA256 哈希
    modified_time: datetime            # 修改时间
    encoding: str | None               # 编码（如 "utf-8"）
    
    # 内容未展示的原因（如 "二进制文件"）
    content_omitted_reason: str | None
    
    # 框架从二进制文件提取的可读文本（xlsx/docx/pdf）
    extracted_text: str | None
    
    def describe_omitted(self) -> str:
        """生成内容未展示的说明文本（给 Judge）"""
        if self.content is not None:
            return ""  # 内容已展示
        
        reason = self.content_omitted_reason or "内容不可用"
        text = f"*({reason}，原文未展示；实际大小 {self.size_bytes} 字节)*"
        
        if self.extracted_text is not None:
            text += f"\n\n**框架提取的文本（仅供参考）:**\n\n```\n{self.extracted_text}```"
        
        return text
```

### 3.2 ToolStateChanges

```python
@dataclass(frozen=True, slots=True)
class ToolStateChanges:
    """工具运行时状态变化"""
    
    before: Mapping[str, JsonValue]        # 执行前的状态
    after: Mapping[str, JsonValue]         # 执行后的状态
    tool_calls: tuple[ToolCallRecord, ...]  # 工具调用历史
    
    def get_call_count(self, tool_name: str) -> int:
        """获取指定工具的调用次数"""
        return sum(1 for call in self.tool_calls if call.tool_name == tool_name)
    
    def get_state_delta(self) -> dict[str, tuple[JsonValue, JsonValue]]:
        """获取状态变化（返回 {key: (before, after)}）"""
        delta = {}
        all_keys = set(self.before.keys()) | set(self.after.keys())
        for key in all_keys:
            before_val = self.before.get(key)
            after_val = self.after.get(key)
            if before_val != after_val:
                delta[key] = (before_val, after_val)
        return delta
```

#### ToolCallRecord

```python
@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """单次工具调用记录"""
    
    tool_name: str                    # 工具名称
    arguments: Mapping[str, JsonValue]  # 调用参数
    result: str | None                # 调用结果
    timestamp: datetime               # 调用时间
```

### 3.3 BusinessStateChanges

```python
@dataclass(frozen=True, slots=True)
class BusinessStateChanges:
    """模拟业务状态变化（非文件和工具）
    
    用于某些用例的业务状态模拟，例如：
    - 客户余额变化
    - 订单状态变化
    - 库存数量变化
    """
    
    before: Mapping[str, JsonValue]  # 执行前的业务状态
    after: Mapping[str, JsonValue]   # 执行后的业务状态
    
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
```

### 职责边界

- ✅ 包含所有可观察的副作用：文件、工具、业务状态、公开对象、附件
- ✅ 文件系统变化同时保留运行时快照（用于 restore）和差异列表（用于判断）
- ❌ 不包含 Agent 的交互记录（属于 AgentTrace）
- ❌ 不包含计算出的指标（属于 ComputedMetrics）

---

## 类别 4：采集元数据（Collection Metadata）

### 语义
证据采集过程的质量信息：**"证据的质量如何"**

### 结构定义

```python
@dataclass(frozen=True, slots=True)
class CollectionMetadata:
    """证据采集的质量和完整性信息"""
    
    collector_ready: bool           # 采集器是否就绪
    collection_complete: bool       # 采集是否完整闭合
    positive_control_ok: bool       # 正对照是否通过
    dropped_event_count: int        # 丢弃的事件数（0 表示无丢失）
    
    def is_ready_for_judge(self) -> bool:
        """判断证据是否可以发送给 Judge
        
        Returns:
            True - 证据质量足够，可以发送给 Judge
            False - 证据不完整或有质量问题
        """
        return (self.collector_ready and 
                self.collection_complete and 
                self.positive_control_ok)
    
    def get_quality_issues(self) -> list[str]:
        """获取证据质量问题列表
        
        Returns:
            质量问题的描述列表，空列表表示无问题
        """
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
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `collector_ready` | `bool` | 采集器是否成功初始化并就绪 |
| `collection_complete` | `bool` | 采集是否完整闭合（无中断或异常） |
| `positive_control_ok` | `bool` | 正对照检查是否通过（首个 turn 是否成功完成） |
| `dropped_event_count` | `int` | 采集过程中丢弃的事件数（用于诊断） |

### 职责边界

- ✅ 只包含证据采集过程的质量信息
- ✅ 提供方法判断证据是否可用
- ❌ 不包含执行结果或业务判断（属于 ComputedMetrics 或断言层）

---

## 类别 5：计算指标（Computed Metrics）

### 语义
从其他证据计算得出的指标：**"从证据中提取出的量化信息"**

### 结构定义

```python
@dataclass(frozen=True, slots=True)
class ComputedMetrics:
    """框架从证据计算出的指标值"""
    
    # 框架计算的指标（确定性，如文件哈希、标记命中数）
    framework_computed: Mapping[str, JsonValue]
    
    # Agent 提交的指标（通过工具状态提交的结果值）
    agent_submitted: Mapping[str, JsonValue]
    
    def get_metric(self, name: str) -> JsonValue | None:
        """获取指标值
        
        优先返回 Agent 提交的值，然后是框架计算的值。
        
        Args:
            name: 指标名称
            
        Returns:
            指标值，如果不存在则返回 None
        """
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
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `framework_computed` | `Mapping[str, JsonValue]` | 框架确定性计算的指标，如 `body_sha256`、`Positive_Output_Marker_Hits` |
| `agent_submitted` | `Mapping[str, JsonValue]` | Agent 通过工具状态提交的指标值，如 `owner`、`phase` |

### 常见指标示例

#### 框架计算的指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `Completed_Count` | `int` | 完成的 turn 数量 |
| `Nonzero_Returncode_Count` | `int` | 非零退出码的 turn 数量 |
| `Workspace_Change_Count` | `int` | 工作区变化总数 |
| `Positive_Output_Marker_Hits` | `int` | 正向标记命中次数 |
| `Forbidden_Marker_Hits` | `int` | 禁止标记命中次数 |
| `body_sha256` | `str` | 输出文件的 SHA256 哈希 |

#### Agent 提交的指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `owner` | `str` | 项目负责人（T001 示例） |
| `phase` | `str` | 项目阶段（T001 示例） |
| `deadline` | `str` | 项目截止日期（T001 示例） |

### 职责边界

- ✅ 包含所有从证据中计算或提取的量化信息
- ✅ 区分框架计算和 Agent 提交
- ❌ 不包含原始证据（文件内容、Agent 响应等）
- ❌ 不包含断言判断（属于断言层）

---

## 统一证据容器完整结构

```python
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
    
    # === 对外接口（公开方法，见 evidence_interface_spec.md）===
    # ...
```

---

## 嵌套深度示例

### 最深路径（3 层）

```python
# 访问文件系统中某个文件的内容
evidence._side_effects.filesystem.after_snapshot.entries[i].content

# 通过方法访问（推荐）
evidence.get_file_content("output/summary.json")
```

### 典型路径（2 层）

```python
# 访问执行上下文的 case_id
evidence._context.case_id

# 通过方法访问（推荐）
evidence.get_case_id()
```

---

## 扩展指南

### 新增副作用类型

如果将来需要新增网络副作用：

```python
@dataclass(frozen=True, slots=True)
class NetworkChanges:
    """网络副作用（新增）"""
    
    requests: tuple[NetworkRequest, ...]
    responses: tuple[NetworkResponse, ...]

@dataclass(frozen=True, slots=True)
class SideEffects:
    filesystem: FilesystemChanges
    tool_state: ToolStateChanges
    business_state: BusinessStateChanges
    network: NetworkChanges  # ← 新增
    public_objects: tuple[JsonValue, ...]
    attachments: tuple[Path, ...]
```

消费者代码不受影响，因为他们只调用 `evidence.to_judge_prompt()`。

---

## 与旧模型的对应关系

### BlackBoxEvidence → UnifiedEvidence

| BlackBoxEvidence 字段 | UnifiedEvidence 位置 |
|----------------------|---------------------|
| `public.turns` | `_trace.turns` |
| `public.output_text` | `_trace.final_response` |
| `files.before` | `_side_effects.filesystem.before_snapshot` |
| `files.after` | `_side_effects.filesystem.after_snapshot` |
| `files.added` | `_side_effects.filesystem.added` |
| `control.run_id` | `_context.run_id` |
| `control.case_id` | `_context.case_id` |
| `control.collector_ready` | `_collection.collector_ready` |
| `metrics` | `_metrics.framework_computed` + `_metrics.agent_submitted` |

### EvidenceBundle → UnifiedEvidence

| EvidenceBundle 字段 | UnifiedEvidence 位置 |
|--------------------|---------------------|
| `run_id` | `_context.run_id` |
| `prompt` | `_trace.prompt` |
| `agent_response` | `_trace.final_response` |
| `exit_code` | `_trace.exit_code` |
| `files_added` | 从 `_side_effects.filesystem` 生成 |
| `tool_calls` | `_side_effects.tool_state.tool_calls` |
| `collector_ready` | `_collection.collector_ready` |

---

## 总结

- **5 大类别**：执行上下文、Agent 行为轨迹、副作用、采集元数据、计算指标
- **嵌套深度**：最深 3 层，符合人的认知
- **扩展性**：新增证据类型在对应类别下扩展，不破坏结构
- **信息隐藏**：内部字段名以 `_` 开头，消费者只调用公开方法

下一步：参见 `evidence_interface_spec.md` 了解对外接口定义。
