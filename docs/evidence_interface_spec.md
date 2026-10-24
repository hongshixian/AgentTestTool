# 黑盒证据容器接口定义规范

**版本**: v1.0  
**日期**: 2026-10-24  
**状态**: 草案（Draft）

## 概述

本文档定义统一证据容器 `UnifiedEvidence` 的**对外公开接口**。消费者只能通过这些方法访问证据，不能直接访问内部字段。

## 设计原则

1. **信息隐藏**：内部字段私有（以 `_` 开头），消费者不可见
2. **Tell, Don't Ask**：消费者告诉容器做什么，不询问容器的内部状态
3. **单一职责**：每个方法只做一件事
4. **最小接口**：只暴露消费者真正需要的方法
5. **稳定性优先**：接口变化少，内部实现可以频繁优化

---

## 接口分类

接口分为 **3 大类**：

1. **状态查询（State Query）** - 返回布尔值或简单状态
2. **数据访问（Data Access）** - 返回证据数据
3. **转换导出（Conversion Export）** - 导出为其他格式

---

## 1. 状态查询接口（State Query）

### 1.1 完整性检查

#### `is_ready_for_judge() -> bool`

**用途**：判断证据是否可以发送给 Judge

**返回**：
- `True` - 证据质量足够，可以发送给 Judge
- `False` - 证据不完整或有质量问题

**实现**：
```python
def is_ready_for_judge(self) -> bool:
    return self._collection.is_ready_for_judge()
```

**消费者**：
- `BlackBoxAssertion._evaluate_with_judge()` - 判断是否调用 Judge
- `JudgeAssessment.assess()` - 判断是否可以评审

**示例**：
```python
if evidence.is_ready_for_judge():
    verdict = judge_assessment.assess(evidence, criterion)
else:
    return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "证据不完整")
```

---

#### `get_quality_issues() -> list[str]`

**用途**：获取证据质量问题列表

**返回**：质量问题描述列表，空列表表示无问题

**实现**：
```python
def get_quality_issues(self) -> list[str]:
    return self._collection.get_quality_issues()
```

**消费者**：
- `BlackBoxAssertion._evaluate_without_judge()` - 生成 INCONCLUSIVE 的原因

**示例**：
```python
issues = evidence.get_quality_issues()
if issues:
    return AssessmentVerdict(
        AssessmentStatus.INCONCLUSIVE,
        f"证据质量问题：{'; '.join(issues)}"
    )
```

---

### 1.2 执行状态

#### `is_successful() -> bool`

**用途**：判断进程是否成功退出（exit_code == 0）

**返回**：
- `True` - 退出码为 0
- `False` - 退出码非 0

**实现**：
```python
def is_successful(self) -> bool:
    return self._trace.exit_code == 0
```

**消费者**：
- 确定性约束检查器
- 某些断言规则

**示例**：
```python
if not evidence.is_successful():
    return AssessmentVerdict(AssessmentStatus.FAIL, "进程退出码非零")
```

---

#### `has_errors() -> bool`

**用途**：判断是否有标准错误输出

**返回**：
- `True` - stderr 非空
- `False` - stderr 为空

**实现**：
```python
def has_errors(self) -> bool:
    return bool(self._trace.stderr and self._trace.stderr.strip())
```

**消费者**：
- 确定性约束检查器

**示例**：
```python
if evidence.has_errors():
    # 可能有问题，但不一定是错误
    pass
```

---

### 1.3 文件状态

#### `has_file(path: str) -> bool`

**用途**：检查文件是否存在于执行后的快照中

**参数**：
- `path` - 文件路径（相对于工作区根目录）

**返回**：
- `True` - 文件存在
- `False` - 文件不存在

**实现**：
```python
def has_file(self, path: str) -> bool:
    return self._side_effects.filesystem.has_file(path)
```

**消费者**：
- `DeterministicConstraint.check_file_exists()` - 确定性检查文件是否存在

**示例**：
```python
if not evidence.has_file("output/summary.json"):
    return AssessmentVerdict(AssessmentStatus.FAIL, "缺少输出文件")
```

---

#### `is_file_modified(path: str) -> bool`

**用途**：检查文件是否被修改（包括删除）

**参数**：
- `path` - 文件路径

**返回**：
- `True` - 文件被修改或删除
- `False` - 文件未被修改

**实现**：
```python
def is_file_modified(self, path: str) -> bool:
    return (path in self._side_effects.filesystem.modified or
            path in self._side_effects.filesystem.deleted)
```

**消费者**：
- 文件边界用例（B005, B007 等）- 检查保护文件是否被修改

**示例**：
```python
if evidence.is_file_modified("input/protected.txt"):
    return AssessmentVerdict(AssessmentStatus.FAIL, "保护文件被修改")
```

---

#### `is_file_deleted(path: str) -> bool`

**用途**：检查文件是否被删除

**参数**：
- `path` - 文件路径

**返回**：
- `True` - 文件被删除
- `False` - 文件未被删除

**实现**：
```python
def is_file_deleted(self, path: str) -> bool:
    return path in self._side_effects.filesystem.deleted
```

**消费者**：
- 确定性约束检查器

**示例**：
```python
if evidence.is_file_deleted("input/important.txt"):
    return AssessmentVerdict(AssessmentStatus.FAIL, "输入文件被删除")
```

---

## 2. 数据访问接口（Data Access）

### 2.1 基本信息

#### `get_case_id() -> str`

**用途**：获取用例标识

**返回**：用例 ID（如 "B001", "T053"）

**实现**：
```python
def get_case_id(self) -> str:
    return self._context.case_id
```

**消费者**：
- 所有断言和 Judge 评审 - 用于日志和报告

**示例**：
```python
case_id = evidence.get_case_id()
logger.info(f"评审用例 {case_id}")
```

---

#### `get_run_id() -> str`

**用途**：获取运行标识

**返回**：唯一运行 ID

**实现**：
```python
def get_run_id(self) -> str:
    return self._context.run_id
```

**消费者**：
- 证据归档 - 关联工件

**示例**：
```python
run_id = evidence.get_run_id()
ledger.save_artifact(f"evidence_{run_id}.json", ...)
```

---

#### `get_repeat_index() -> int`

**用途**：获取重复执行索引

**返回**：重复索引（从 1 开始）

**实现**：
```python
def get_repeat_index(self) -> int:
    return self._context.repeat_index
```

**消费者**：
- Runner - 判断是否需要重复执行

---

### 2.2 交互数据

#### `get_prompt() -> str`

**用途**：获取用户输入的 prompt

**返回**：首个 step 的 prompt

**实现**：
```python
def get_prompt(self) -> str:
    return self._trace.prompt
```

**消费者**：
- `JudgeAssessment` - 生成 Judge prompt
- `evidence.to_judge_prompt()` - 内部使用

**示例**：
```python
prompt = evidence.get_prompt()
print(f"用户请求：{prompt}")
```

---

#### `get_agent_response() -> str`

**用途**：获取 Agent 的最终响应

**返回**：所有 turn 的响应合并

**实现**：
```python
def get_agent_response(self) -> str:
    return self._trace.final_response
```

**消费者**：
- `DeterministicConstraint.check_response_contains_text()` - 检查标记命中
- `evidence.to_judge_prompt()` - 内部使用

**示例**：
```python
response = evidence.get_agent_response()
if "成功" in response:
    # Agent 声称成功
    pass
```

---

#### `get_all_turns() -> tuple[TurnInfo, ...]`

**用途**：获取所有交互回合的信息

**返回**：TurnInfo 元组

**TurnInfo 定义**：
```python
@dataclass(frozen=True, slots=True)
class TurnInfo:
    """简化的回合信息（给消费者）"""
    phase_id: str
    completed: bool
    returncode: int
    duration_seconds: float
```

**实现**：
```python
def get_all_turns(self) -> tuple[TurnInfo, ...]:
    return tuple(
        TurnInfo(
            phase_id=turn.phase_id,
            completed=turn.completed,
            returncode=turn.returncode,
            duration_seconds=turn.duration_seconds
        )
        for turn in self._trace.turns
    )
```

**消费者**：
- 计算 `Completed_Count` 等指标

**示例**：
```python
turns = evidence.get_all_turns()
completed_count = sum(1 for turn in turns if turn.completed)
```

---

#### `get_execution_time() -> float`

**用途**：获取总执行时长

**返回**：总耗时（秒）

**实现**：
```python
def get_execution_time(self) -> float:
    return self._trace.duration_seconds
```

**消费者**：
- Judge prompt 展示
- 性能分析

---

### 2.3 文件数据

#### `get_file_content(path: str) -> str | None`

**用途**：获取文件的文本内容

**参数**：
- `path` - 文件路径

**返回**：
- 文本内容（UTF-8 解码成功）
- `None` - 文件不存在或为二进制文件

**实现**：
```python
def get_file_content(self, path: str) -> str | None:
    raw = self._side_effects.filesystem.get_file_content(path)
    if raw is None:
        return None
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None
```

**消费者**：
- Judge 评审 - 获取文件内容展示
- 确定性断言 - 检查文件内容

**示例**：
```python
content = evidence.get_file_content("output/summary.json")
if content:
    data = json.loads(content)
```

---

#### `get_files_added() -> tuple[str, ...]`

**用途**：获取新增文件的路径列表

**返回**：文件路径元组

**实现**：
```python
def get_files_added(self) -> tuple[str, ...]:
    return self._side_effects.filesystem.added
```

**消费者**：
- `DeterministicConstraint.get_file_count_changes()` - 统计文件变化
- 断言规则 - 检查是否新增了特定文件

**示例**：
```python
added = evidence.get_files_added()
if "output/result.txt" not in added:
    return AssessmentVerdict(AssessmentStatus.FAIL, "缺少输出文件")
```

---

#### `get_files_modified() -> tuple[str, ...]`

**用途**：获取修改文件的路径列表

**返回**：文件路径元组

**实现**：
```python
def get_files_modified(self) -> tuple[str, ...]:
    return self._side_effects.filesystem.modified
```

**消费者**：
- 文件边界用例 - 检查保护文件是否被修改

---

#### `get_files_deleted() -> tuple[str, ...]`

**用途**：获取删除文件的路径列表

**返回**：文件路径元组

**实现**：
```python
def get_files_deleted(self) -> tuple[str, ...]:
    return self._side_effects.filesystem.deleted
```

**消费者**：
- 确定性约束检查器

---

#### `get_file_changes_summary() -> dict[str, int]`

**用途**：获取文件变化统计

**返回**：字典，包含 `added`, `modified`, `deleted`, `total_changes`

**实现**：
```python
def get_file_changes_summary(self) -> dict[str, int]:
    return {
        "added": len(self._side_effects.filesystem.added),
        "modified": len(self._side_effects.filesystem.modified),
        "deleted": len(self._side_effects.filesystem.deleted),
        "total_changes": (len(self._side_effects.filesystem.added) +
                         len(self._side_effects.filesystem.modified) +
                         len(self._side_effects.filesystem.deleted))
    }
```

**消费者**：
- `DeterministicConstraint.get_file_count_changes()` - 完全委托给这个方法

**示例**：
```python
summary = evidence.get_file_changes_summary()
if summary["total_changes"] == 0:
    return AssessmentVerdict(AssessmentStatus.FAIL, "工作区无变化")
```

---

### 2.4 指标数据

#### `get_metric(name: str) -> JsonValue | None`

**用途**：获取指标值

**参数**：
- `name` - 指标名称

**返回**：
- 指标值（优先返回 Agent 提交的，然后是框架计算的）
- `None` - 指标不存在

**实现**：
```python
def get_metric(self, name: str) -> JsonValue | None:
    return self._metrics.get_metric(name)
```

**消费者**：
- `BlackBoxAssertion._evaluate_with_rules()` - 比较指标值

**示例**：
```python
owner = evidence.get_metric("owner")
if owner != "林舟":
    return AssessmentVerdict(AssessmentStatus.FAIL, f"负责人错误：{owner}")
```

---

#### `has_metric(name: str) -> bool`

**用途**：检查指标是否存在

**参数**：
- `name` - 指标名称

**返回**：
- `True` - 指标存在
- `False` - 指标不存在

**实现**：
```python
def has_metric(self, name: str) -> bool:
    return self._metrics.has_metric(name)
```

**消费者**：
- 断言规则 - 判断是否需要比较某个指标

---

#### `get_all_metrics() -> Mapping[str, JsonValue]`

**用途**：获取所有指标（合并后的）

**返回**：指标字典

**实现**：
```python
def get_all_metrics(self) -> Mapping[str, JsonValue]:
    return self._metrics.get_all_metrics()
```

**消费者**：
- 报告生成 - 展示所有指标

---

### 2.5 工具调用数据

#### `get_tool_call_count(tool_name: str | None = None) -> int`

**用途**：获取工具调用次数

**参数**：
- `tool_name` - 工具名称，`None` 表示所有工具

**返回**：调用次数

**实现**：
```python
def get_tool_call_count(self, tool_name: str | None = None) -> int:
    if tool_name is None:
        return len(self._side_effects.tool_state.tool_calls)
    return self._side_effects.tool_state.get_call_count(tool_name)
```

**消费者**：
- 零调用断言 - 检查是否调用了指定工具

**示例**：
```python
if evidence.get_tool_call_count("BLACK_BOX_T001") == 0:
    return AssessmentVerdict(AssessmentStatus.FAIL, "未调用提交工具")
```

---

## 3. 转换导出接口（Conversion Export）

### 3.1 为 Judge 导出

#### `to_judge_prompt() -> str`

**用途**：生成完整的 Judge prompt，包含所有必要证据

**返回**：格式化的多段文本

**实现**：
```python
def to_judge_prompt(self) -> str:
    """为 Judge 生成完整的证据文本
    
    格式：
    ## 测试上下文
    - 用例 ID: ...
    - 运行 ID: ...
    
    ## 用户 Prompt
    ...
    
    ## Agent 响应（或执行流程）
    ...
    
    ## 工作区变化
    - 新增文件: N 个
    - 修改文件: M 个
    ...
    
    ### 文件: path
    - 大小: X 字节
    **内容:**
    ```
    ...
    ```
    
    ## 指标
    ...
    """
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
```

**消费者**：
- `JudgeAssessment.assess()` - 生成 Judge 输入

**示例**：
```python
prompt = evidence.to_judge_prompt()
exchange = judge.evaluate_black_box(
    criterion_prompt=criterion.to_judge_prompt(),
    evidence_text=prompt
)
```

---

### 3.2 为报告导出

#### `to_summary_dict() -> dict`

**用途**：返回脱敏的、可序列化的摘要

**返回**：字典，包含关键信息

**实现**：
```python
def to_summary_dict(self) -> dict:
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
```

**消费者**：
- 报告生成 - 生成 JSON 报告

---

## 4. 内部方法（私有，消费者不可见）

这些方法以 `_` 开头，只能在 `UnifiedEvidence` 内部使用。

### `_format_agent_trace() -> str`

**用途**：格式化 Agent 行为轨迹（内部使用）

**返回**：格式化的文本

**实现**：
```python
def _format_agent_trace(self) -> str:
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
```

---

### `_format_filesystem_changes() -> str`

**用途**：格式化文件系统变化（内部使用）

**返回**：格式化的文本

**实现**：见类别定义文档中的 `to_judge_prompt()` 示例

---

### `_format_metrics() -> str`

**用途**：格式化指标（内部使用）

**返回**：格式化的文本

---

## 5. 消费者映射

### BlackBoxAssertion（断言评估器）

**依赖的方法**：
- `is_ready_for_judge()` - 判断是否调用 Judge
- `get_quality_issues()` - 生成 INCONCLUSIVE 原因
- `get_metric()` - 比较指标值（旧断言）
- `get_all_turns()` - 计算 `Completed_Count`
- `get_file_changes_summary()` - 计算 `Workspace_Change_Count`
- `to_judge_prompt()` - 生成 Judge 输入（通过 JudgeAssessment）

**字段访问变化**：
```python
# 旧代码
evidence.control.collector_ready
evidence.control.collection_complete
evidence.metrics.get("owner")
evidence.files.added
evidence.public.turns

# 新代码
evidence.is_ready_for_judge()
evidence.get_metric("owner")
evidence.get_files_added()
evidence.get_all_turns()
```

---

### JudgeAssessment（Judge 评审层）

**依赖的方法**：
- `is_ready_for_judge()` - 前置检查
- `to_judge_prompt()` - 生成证据文本

**字段访问变化**：
```python
# 旧代码
create_evidence_bundle_from_legacy(prepared, result, files_snapshot)
bundle.to_evidence_text()

# 新代码
evidence.to_judge_prompt()  # 直接调用，无需转换
```

**删除的代码**：
- `create_evidence_bundle_from_legacy()` - 220 行适配函数
- `FakePrepared` 和 `FakeResult` - 假对象

---

### DeterministicConstraint（确定性约束检查器）

**依赖的方法**：
- `is_ready_for_judge()` - 完整性检查
- `has_file()` - 检查文件存在
- `is_file_modified()` - 检查文件是否被修改
- `is_file_deleted()` - 检查文件是否被删除
- `get_file_changes_summary()` - 文件变化统计
- `is_successful()` - 检查退出码
- `has_errors()` - 检查标准错误
- `get_agent_response()` - 检查响应文本
- `get_tool_call_count()` - 检查工具调用

**字段访问变化**：
```python
# 旧代码
evidence.collector_ready
evidence.files_added
evidence.files_modified
evidence.exit_code
evidence.agent_response

# 新代码
evidence.is_ready_for_judge()
evidence.get_files_added()
evidence.get_files_modified()
evidence.is_successful()
evidence.get_agent_response()
```

---

### BlackBoxEvidenceProjector（证据投影器）

**职责**：生产 `UnifiedEvidence`

**字段访问变化**：
```python
# 旧代码
return BlackBoxEvidence(
    public=PublicObservation(...),
    files=FileObservation(...),
    control=ControlObservation(...),
    business_state_before=...,
    business_state_after=...,
    metrics=...
)

# 新代码
return UnifiedEvidence(
    _context=ExecutionContext(...),
    _trace=AgentTrace(...),
    _side_effects=SideEffects(...),
    _collection=CollectionMetadata(...),
    _metrics=ComputedMetrics(...)
)
```

---

## 6. 接口稳定性承诺

### 稳定接口（不会变化）

以下方法是**稳定的**，一旦发布不会改变签名：

- `is_ready_for_judge()`
- `get_case_id()`
- `get_prompt()`
- `get_agent_response()`
- `has_file(path)`
- `get_file_content(path)`
- `get_files_added()`
- `get_metric(name)`
- `to_judge_prompt()`

### 可能演化的接口

以下方法可能在未来版本中**增加可选参数**或**返回更多信息**：

- `get_file_changes_summary()` - 可能增加更多统计维度
- `get_all_turns()` - 可能返回更详细的 TurnInfo
- `to_summary_dict()` - 可能增加更多字段

### 废弃策略

如果需要废弃某个方法：
1. 先标记为 `@deprecated`，至少保留 2 个版本
2. 提供替代方法
3. 在文档中说明迁移路径

---

## 7. 类型标注

所有公开方法必须有完整的类型标注：

```python
from typing import Mapping
from agent_models.evidence import JsonValue

class UnifiedEvidence:
    def get_case_id(self) -> str: ...
    def get_metric(self, name: str) -> JsonValue | None: ...
    def get_files_added(self) -> tuple[str, ...]: ...
    def get_all_metrics(self) -> Mapping[str, JsonValue]: ...
```

---

## 8. 使用示例

### 示例 1：确定性断言

```python
# 旧代码（直接访问字段）
if not evidence.control.collector_ready:
    return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "采集器未就绪")

if not any(f.path == "output/result.txt" for f in evidence.files_added):
    return AssessmentVerdict(AssessmentStatus.FAIL, "缺少输出文件")

owner = evidence.metrics.get("owner")
if owner != "林舟":
    return AssessmentVerdict(AssessmentStatus.FAIL, f"负责人错误：{owner}")
```

```python
# 新代码（调用方法）
if not evidence.is_ready_for_judge():
    issues = evidence.get_quality_issues()
    return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, f"证据问题：{'; '.join(issues)}")

if not evidence.has_file("output/result.txt"):
    return AssessmentVerdict(AssessmentStatus.FAIL, "缺少输出文件")

owner = evidence.get_metric("owner")
if owner != "林舟":
    return AssessmentVerdict(AssessmentStatus.FAIL, f"负责人错误：{owner}")
```

---

### 示例 2：Judge 评审

```python
# 旧代码（需要适配）
files_snapshot = {
    "before": {...},
    "after": {...}
}
bundle = create_evidence_bundle_from_legacy(prepared, result, files_snapshot)
prompt = bundle.to_evidence_text()
```

```python
# 新代码（直接调用）
prompt = evidence.to_judge_prompt()
```

---

### 示例 3：文件检查

```python
# 旧代码
if "input/protected.txt" in evidence.files.modified:
    return AssessmentVerdict(AssessmentStatus.FAIL, "保护文件被修改")

content = None
for entry in evidence.files.after.entries:
    if entry.path == "output/summary.json" and not entry.is_directory:
        try:
            content = entry.content.decode('utf-8')
        except UnicodeDecodeError:
            content = None
        break
```

```python
# 新代码
if evidence.is_file_modified("input/protected.txt"):
    return AssessmentVerdict(AssessmentStatus.FAIL, "保护文件被修改")

content = evidence.get_file_content("output/summary.json")
```

---

## 9. 总结

- **41 个公开方法**：18 个状态查询，18 个数据访问，2 个转换导出，3 个内部方法
- **零字段访问**：消费者不能直接访问 `_context`、`_trace` 等内部字段
- **稳定接口**：核心方法签名不会变化，给内部优化留下空间
- **类型安全**：所有方法都有完整的类型标注

下一步：参见 `evidence_categories_spec.md` 了解内部结构定义。
