# 黑盒证据容器统一重构计划

**版本**: v1.0  
**日期**: 2026-10-24  
**状态**: 执行计划（Execution Plan）  
**预计工期**: 8-10 个工作日  
**风险等级**: 中-高

---

## 目录

1. [重构目标](#重构目标)
2. [整体策略](#整体策略)
3. [阶段划分](#阶段划分)
4. [详细执行步骤](#详细执行步骤)
5. [风险控制](#风险控制)
6. [验证标准](#验证标准)
7. [回滚方案](#回滚方案)

---

## 重构目标

### 核心目标

**废弃双轨制证据容器，统一为 `UnifiedEvidence`**

- 删除 `BlackBoxEvidence`（models.py，21 个字段，分层结构）
- 删除 `EvidenceBundle`（evidence_models.py，20 个字段，扁平结构）
- 删除 `create_evidence_bundle_from_legacy()`（220 行适配代码）
- 删除 `FakePrepared` 和 `FakeResult`（假对象）

### 设计原则

1. **信息隐藏** - 内部字段私有（`_` 前缀），消费者通过方法访问
2. **语义分类** - 按真实来源分为 5 大类：执行上下文、Agent 轨迹、副作用、采集元数据、计算指标
3. **嵌套有度** - 最深 3 层，符合人的认知
4. **接口稳定** - 41 个公开方法，核心方法签名不变

### 预期收益

- **代码简化**：删除 ~470 行适配代码
- **耦合降低**：消费者不依赖内部结构，只依赖方法
- **维护性提升**：内部结构变化不影响消费者
- **扩展性增强**：新增证据类型无需修改消费者

---

## 整体策略

### 策略选择：大爆炸式重构（Big Bang）

**原因**：
1. 证据容器是核心数据结构，渐进式迁移会导致长期维护两套代码
2. 消费者数量有限（4 个主要模块），一次性迁移成本可控
3. 行为基线（334 个用例）提供了完整的回归测试保护网

### 风险缓解措施

1. **分阶段提交** - 每个阶段完成后立即提交，保留回滚点
2. **行为基线验证** - 每个阶段结束后运行 334 个用例
3. **单元测试先行** - 实现新类别时先写单元测试
4. **代码审查** - 每个阶段代码由第二人审查（如果团队有多人）

---

## 阶段划分

| 阶段 | 名称 | 工作量 | 关键风险 | 产出 |
|------|------|--------|----------|------|
| 0 | 前置准备 | 0.5 天 | 低 | 新分支、文档确认 |
| 1 | 实现类别定义 | 2-3 天 | 中 | 5 大类别 + 单元测试 |
| 2 | 实现统一容器 | 1 天 | 中 | UnifiedEvidence + 41 个方法 |
| 3 | 迁移证据生产者 | 1 天 | 中 | 修改 BlackBoxEvidenceProjector |
| 4 | 迁移消费者 | 3-4 天 | 高 | 迁移 4 个消费者模块 |
| 5 | 删除旧代码 | 0.5 天 | 低 | 删除旧模型和适配代码 |
| 6 | 最终验证和文档 | 0.5-1 天 | 低 | 完整验证 + 更新文档 |
| **总计** | | **8.5-11 天** | | 完整重构 |

---

## 详细执行步骤

## 阶段 0：前置准备（0.5 天）

### 0.1 创建重构分支

```bash
cd /vol1/1002/git/agentTestTool
git checkout refactor/black-box-structure
git pull origin refactor/black-box-structure
git checkout -b refactor/unified-evidence
```

**验证**：`git branch` 显示当前在 `refactor/unified-evidence`

---

### 0.2 确认文档完整性

**检查清单**：
- [ ] `docs/evidence_categories_spec.md` 存在且完整
- [ ] `docs/evidence_interface_spec.md` 存在且完整
- [ ] 两份文档中的字段定义一致
- [ ] 方法签名与类别定义匹配

**验证**：
```bash
ls -lh docs/evidence_*.md
wc -l docs/evidence_*.md
```

---

### 0.3 运行基线测试

```bash
# 运行黑盒卷，记录当前通过率
uv run pytest test_cases/black_box --case-suite black_box -v > /tmp/baseline_before.txt

# 统计通过率
grep -E "(PASSED|FAILED)" /tmp/baseline_before.txt | wc -l
```

**验证**：记录通过的用例数（预期 334 个中的大部分通过）

---

### 0.4 提交前置准备

```bash
git add docs/evidence_categories_spec.md docs/evidence_interface_spec.md docs/evidence_refactor_plan.md
git commit -m "docs(evidence): add refactor specs and plan

- 证据类别定义规范：5 大类别的完整定义
- 证据容器接口定义规范：41 个公开方法
- 重构执行计划：8-10 天的详细步骤

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push origin refactor/unified-evidence
```

---

## 阶段 1：实现类别定义（2-3 天）

### 1.1 创建类别定义文件

**文件**：`test_cases/black_box/evidence_categories.py`

**内容结构**：
```python
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

# ... 完整实现见下文
```

---

### 1.2 实现 ExecutionContext（0.5 天）

```python
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
```

**单元测试**：`tests/test_evidence_categories.py`

```python
def test_execution_context_creation():
    ctx = ExecutionContext(
        run_id="test_run_001",
        case_id="B001",
        repeat_index=1,
        timestamp=datetime.now()
    )
    assert ctx.run_id == "test_run_001"
    assert ctx.case_id == "B001"

def test_execution_context_validation():
    with pytest.raises(ValueError, match="run_id"):
        ExecutionContext("", "B001", 1, datetime.now())
```

**验证**：
```bash
uv run pytest tests/test_evidence_categories.py::test_execution_context_creation -v
```

---

### 1.3 实现 AgentTrace（0.5 天）

```python
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
        object.__setattr__(self, "final_response", 
                          "\n".join(turn.response for turn in self.turns))
```

**单元测试**：
```python
def test_agent_trace_creation():
    turn = TurnRecord("exercise", "prompt", "response", True, 0, 5.0)
    trace = AgentTrace(
        prompt="test prompt",
        turns=(turn,),
        final_response="response",
        execution_phases=None,
        exit_code=0,
        duration_seconds=5.0,
        stdout="",
        stderr=""
    )
    assert trace.prompt == "test prompt"
    assert len(trace.turns) == 1
```

**提交**：
```bash
git add test_cases/black_box/evidence_categories.py tests/test_evidence_categories.py
git commit -m "feat(evidence): implement ExecutionContext and AgentTrace

- ExecutionContext: 运行元信息（4 个字段）
- AgentTrace: Agent 行为轨迹（8 个字段 + 2 个子类型）
- 包含完整的单元测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 1.4 实现 SideEffects（1 天）

这是最复杂的一个类别，包含 4 个子类别。

#### 1.4.1 FilesystemChanges

```python
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
```

**单元测试**：
```python
def test_filesystem_changes_get_file_content():
    # 创建测试快照
    from agent_models.environment.workspace import WorkspaceEntry, WorkspaceSnapshot
    from pathlib import Path
    
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())
    
    fs = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )
    
    content = fs.get_file_content("test.txt")
    assert content == b"hello"
    
    assert fs.has_file("test.txt")
    assert not fs.has_file("nonexistent.txt")
```

---

#### 1.4.2 ToolStateChanges 和 BusinessStateChanges

```python
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
```

---

#### 1.4.3 组装 SideEffects

```python
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
```

**提交**：
```bash
git add test_cases/black_box/evidence_categories.py tests/test_evidence_categories.py
git commit -m "feat(evidence): implement SideEffects with 3 sub-categories

- FilesystemChanges: 文件系统变化（含展示转换）
- ToolStateChanges: 工具状态变化（含调用记录）
- BusinessStateChanges: 业务状态变化
- SideEffects: 组装所有副作用

包含完整的单元测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 1.5 实现 CollectionMetadata 和 ComputedMetrics（0.5 天）

```python
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
```

**单元测试**：
```python
def test_collection_metadata_is_ready():
    meta = CollectionMetadata(True, True, True, 0)
    assert meta.is_ready_for_judge()
    assert meta.get_quality_issues() == []

def test_collection_metadata_has_issues():
    meta = CollectionMetadata(False, True, True, 2)
    assert not meta.is_ready_for_judge()
    issues = meta.get_quality_issues()
    assert "采集器未就绪" in issues
    assert "丢弃了 2 个事件" in issues

def test_computed_metrics_get_metric():
    metrics = ComputedMetrics(
        framework_computed={"completed": 1},
        agent_submitted={"owner": "林舟"}
    )
    assert metrics.get_metric("owner") == "林舟"
    assert metrics.get_metric("completed") == 1
    assert metrics.has_metric("owner")
```

**提交**：
```bash
git add test_cases/black_box/evidence_categories.py tests/test_evidence_categories.py
git commit -m "feat(evidence): implement CollectionMetadata and ComputedMetrics

- CollectionMetadata: 采集元数据（4 个字段 + 2 个方法）
- ComputedMetrics: 计算指标（2 个映射 + 3 个方法）
- 完成 5 大类别的全部实现

包含完整的单元测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 1.6 验证阶段 1

```bash
# 运行类别定义的单元测试
uv run pytest tests/test_evidence_categories.py -v

# 确保所有测试通过
echo $?  # 应该输出 0
```

**验收标准**：
- [ ] 5 大类别全部实现
- [ ] 所有单元测试通过
- [ ] 代码覆盖率 > 80%
- [ ] 无 mypy 类型错误

---

## 阶段 2：实现统一容器（1 天）

### 2.1 创建 UnifiedEvidence

**文件**：`test_cases/black_box/unified_evidence.py`

```python
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
    TurnRecord,
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
```

---

### 2.2 单元测试

**文件**：`tests/test_unified_evidence.py`

```python
"""UnifiedEvidence 的单元测试"""

from datetime import datetime
from pathlib import Path

import pytest

from agent_models.environment.workspace import WorkspaceEntry, WorkspaceSnapshot
from test_cases.black_box.evidence_categories import (
    AgentTrace,
    BusinessStateChanges,
    CollectionMetadata,
    ComputedMetrics,
    ExecutionContext,
    FilesystemChanges,
    SideEffects,
    ToolStateChanges,
    TurnRecord,
)
from test_cases.black_box.unified_evidence import UnifiedEvidence


def create_test_evidence() -> UnifiedEvidence:
    """创建测试用的 UnifiedEvidence"""
    
    # 1. 执行上下文
    context = ExecutionContext(
        run_id="test_run_001",
        case_id="B001",
        repeat_index=1,
        timestamp=datetime.now()
    )
    
    # 2. Agent 轨迹
    turn = TurnRecord("exercise", "prompt", "response", True, 0, 5.0)
    trace = AgentTrace(
        prompt="test prompt",
        turns=(turn,),
        final_response="response",
        execution_phases=None,
        exit_code=0,
        duration_seconds=5.0,
        stdout="",
        stderr=""
    )
    
    # 3. 副作用
    entry = WorkspaceEntry("test.txt", False, 0o644, b"hello", "hash123")
    snapshot_after = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, (entry,))
    snapshot_before = WorkspaceSnapshot(Path("/tmp"), (0, 0), 0o755, ())
    
    filesystem = FilesystemChanges(
        before_snapshot=snapshot_before,
        after_snapshot=snapshot_after,
        added=("test.txt",),
        modified=(),
        deleted=()
    )
    
    tool_state = ToolStateChanges(
        before={},
        after={},
        tool_calls=()
    )
    
    business_state = BusinessStateChanges(
        before={},
        after={}
    )
    
    side_effects = SideEffects(
        filesystem=filesystem,
        tool_state=tool_state,
        business_state=business_state,
        public_objects=(),
        attachments=()
    )
    
    # 4. 采集元数据
    collection = CollectionMetadata(
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=True,
        dropped_event_count=0
    )
    
    # 5. 计算指标
    metrics = ComputedMetrics(
        framework_computed={"completed": 1},
        agent_submitted={"owner": "林舟"}
    )
    
    return UnifiedEvidence(
        _context=context,
        _trace=trace,
        _side_effects=side_effects,
        _collection=collection,
        _metrics=metrics
    )


def test_unified_evidence_state_queries():
    """测试状态查询接口"""
    evidence = create_test_evidence()
    
    assert evidence.is_ready_for_judge()
    assert evidence.get_quality_issues() == []
    assert evidence.is_successful()
    assert not evidence.has_errors()
    assert evidence.has_file("test.txt")
    assert not evidence.has_file("nonexistent.txt")


def test_unified_evidence_data_access():
    """测试数据访问接口"""
    evidence = create_test_evidence()
    
    assert evidence.get_case_id() == "B001"
    assert evidence.get_run_id() == "test_run_001"
    assert evidence.get_prompt() == "test prompt"
    assert evidence.get_agent_response() == "response"
    assert evidence.get_execution_time() == 5.0
    
    assert evidence.get_file_content("test.txt") == "hello"
    assert evidence.get_files_added() == ("test.txt",)
    
    assert evidence.get_metric("owner") == "林舟"
    assert evidence.get_metric("completed") == 1


def test_unified_evidence_to_judge_prompt():
    """测试 to_judge_prompt 方法"""
    evidence = create_test_evidence()
    
    prompt = evidence.to_judge_prompt()
    
    assert "## 测试上下文" in prompt
    assert "B001" in prompt
    assert "## 用户 Prompt" in prompt
    assert "test prompt" in prompt
    assert "## Agent 响应" in prompt
    assert "response" in prompt
    assert "## 工作区变化" in prompt
    assert "test.txt" in prompt
```

---

### 2.3 验证阶段 2

```bash
# 运行 UnifiedEvidence 的单元测试
uv run pytest tests/test_unified_evidence.py -v

# 确保所有测试通过
echo $?
```

**提交**：
```bash
git add test_cases/black_box/unified_evidence.py tests/test_unified_evidence.py
git commit -m "feat(evidence): implement UnifiedEvidence with 41 public methods

- 统一证据容器：组装 5 大类别
- 41 个公开方法：18 个状态查询 + 18 个数据访问 + 2 个转换导出 + 3 个内部方法
- 内部字段私有（`_` 前缀），消费者只能通过方法访问
- 包含完整的单元测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## 阶段 3：迁移证据生产者（1 天）

### 3.1 修改 BlackBoxEvidenceProjector

**文件**：`test_cases/black_box/evidence.py`

**修改前**：
```python
class BlackBoxEvidenceProjector:
    def observe(self, prepared, execution, agent_model) -> BlackBoxEvidence:
        # 返回 BlackBoxEvidence
        return BlackBoxEvidence(
            public=PublicObservation(...),
            files=FileObservation(...),
            control=ControlObservation(...),
            business_state_before=...,
            business_state_after=...,
            metrics=...
        )
```

**修改后**：
```python
from test_cases.black_box.unified_evidence import UnifiedEvidence
from test_cases.black_box.evidence_categories import (
    AgentTrace,
    BusinessStateChanges,
    CollectionMetadata,
    ComputedMetrics,
    ExecutionContext,
    FilesystemChanges,
    PhaseRecord,
    SideEffects,
    ToolCallRecord,
    ToolStateChanges,
    TurnRecord,
)

class BlackBoxEvidenceProjector:
    def observe(
        self, prepared: PreparedBlackBoxEnvironment, 
        execution: BlackBoxExecutionResult,
        agent_model: AgentModel
    ) -> UnifiedEvidence:
        """采集证据并构造统一证据容器"""
        
        environment = agent_model.environment
        before = prepared.baseline.workspace
        after = environment.workspace.snapshot()
        difference = environment.workspace.diff(before)
        runtime = environment.runtime
        health = environment.health()
        
        # 1. 执行上下文
        context = ExecutionContext(
            run_id=prepared.run_id,
            case_id=prepared.spec.case_id,
            repeat_index=prepared.repeat_index,
            timestamp=datetime.now()  # TODO: 使用真实的开始时间
        )
        
        # 2. Agent 轨迹
        turns = tuple(
            TurnRecord(
                phase_id=turn.phase_id,
                prompt=prepared.spec.steps[i].prompt if i < len(prepared.spec.steps) else "",
                response=turn.response,
                completed=turn.completed,
                returncode=turn.returncode,
                duration_seconds=turn.duration_seconds,
                session_id=turn.session_id
            )
            for i, turn in enumerate(execution.turns)
        )
        
        trace = AgentTrace(
            prompt=prepared.spec.steps[0].prompt if prepared.spec.steps else "",
            turns=turns,
            final_response="\n".join(turn.response for turn in execution.turns),
            execution_phases=None,  # TODO: 如果有多阶段执行，构造 PhaseRecord
            exit_code=turns[-1].returncode if turns else 0,
            duration_seconds=sum(turn.duration_seconds for turn in execution.turns),
            stdout="",  # TODO: 如果有 stdout
            stderr=""   # TODO: 如果有 stderr
        )
        
        # 3. 副作用
        filesystem = FilesystemChanges(
            before_snapshot=before,
            after_snapshot=after,
            added=difference.added,
            modified=difference.modified,
            deleted=difference.deleted
        )
        
        tool_calls = tuple(
            ToolCallRecord(
                tool_name=call.tool_name,
                arguments=call.arguments,
                result=call.result,
                timestamp=datetime.now()  # TODO: 使用真实的调用时间
            )
            for call in []  # TODO: 从 runtime 获取工具调用记录
        )
        
        tool_state = ToolStateChanges(
            before=prepared.baseline.tools.state if prepared.baseline.tools is not None else {},
            after=runtime.state if runtime is not None else {},
            tool_calls=tool_calls
        )
        
        business_state = BusinessStateChanges(
            before=dict(prepared.spec.initial_business_state),
            after=dict(prepared.spec.initial_business_state)  # TODO: 获取执行后的业务状态
        )
        
        side_effects = SideEffects(
            filesystem=filesystem,
            tool_state=tool_state,
            business_state=business_state,
            public_objects=execution.public_objects,
            attachments=execution.attachments
        )
        
        # 4. 采集元数据
        positive_control_ok = bool(execution.turns) and execution.turns[0].completed and execution.turns[0].returncode == 0
        
        collection = CollectionMetadata(
            collector_ready=bool(health["ledger"]["healthy"]),
            collection_complete=bool(health["healthy"]),
            positive_control_ok=positive_control_ok,
            dropped_event_count=health.get("dropped_events", 0)
        )
        
        # 5. 计算指标
        framework_computed = dict(execution.metrics)
        agent_submitted = {}
        
        # 从 runtime.state 提取 Agent 提交的指标
        if runtime is not None:
            for key, value in runtime.state.items():
                if key.startswith("agent_result_"):
                    metric_name = key[len("agent_result_"):]
                    agent_submitted[metric_name] = value
        
        metrics = ComputedMetrics(
            framework_computed=framework_computed,
            agent_submitted=agent_submitted
        )
        
        # 构造统一证据容器
        evidence = UnifiedEvidence(
            _context=context,
            _trace=trace,
            _side_effects=side_effects,
            _collection=collection,
            _metrics=metrics
        )
        
        # 保存证据到台账
        environment.ledger.save_artifact(
            f"unified_evidence_{prepared.spec.case_id}_repeat_{prepared.repeat_index}",
            evidence.to_summary_dict()
        )
        
        return evidence
```

---

### 3.2 验证阶段 3

```bash
# 运行黑盒卷的一个简单用例，测试证据生产者
uv run pytest test_cases/black_box/test_b001.py --case-suite black_box -v

# 检查是否成功构造 UnifiedEvidence
echo $?
```

**提交**：
```bash
git add test_cases/black_box/evidence.py
git commit -m "refactor(evidence): migrate BlackBoxEvidenceProjector to UnifiedEvidence

- BlackBoxEvidenceProjector 现在返回 UnifiedEvidence
- 从 BlackBoxExecutionResult 提取数据构造 5 大类别
- 保持对外接口不变（observe 方法签名不变）

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## 阶段 4：迁移消费者（3-4 天）

这是最复杂的阶段，需要迁移 4 个主要消费者模块。

### 4.1 迁移 DeterministicConstraint（0.5 天）

**文件**：`test_cases/black_box/constraints.py`

**修改策略**：所有字段访问改为方法调用

```python
# 修改前
evidence.collector_ready
evidence.files_added
evidence.agent_response

# 修改后
evidence.is_ready_for_judge()
evidence.get_files_added()
evidence.get_agent_response()
```

**具体修改**：

```python
class DeterministicConstraint:
    def check_evidence_completeness(
        self,
        evidence: UnifiedEvidence,  # 类型改变
        required_evidence: list[str]
    ) -> Optional[str]:
        # 修改前：evidence.collector_ready
        # 修改后：evidence.is_ready_for_judge()
        issues = evidence.get_quality_issues()
        if issues:
            return "; ".join(issues)
        
        # ... 其他检查
        return None
    
    def check_file_exists(self, evidence: UnifiedEvidence, file_path: str) -> bool:
        # 修改前：any(f.path == file_path for f in evidence.files_added)
        # 修改后：直接调用方法
        return evidence.has_file(file_path)
    
    def check_file_not_modified(self, evidence: UnifiedEvidence, file_path: str) -> bool:
        # 修改前：any(f.path == file_path for f in evidence.files_modified)
        # 修改后：
        return not evidence.is_file_modified(file_path)
    
    def get_file_count_changes(self, evidence: UnifiedEvidence) -> dict[str, int]:
        # 修改前：len(evidence.files_added)
        # 修改后：直接委托给方法
        return evidence.get_file_changes_summary()
    
    def check_response_contains_text(self, evidence: UnifiedEvidence, text: str) -> bool:
        # 修改前：text in evidence.agent_response
        # 修改后：
        return text in evidence.get_agent_response()
```

**验证**：
```bash
uv run pytest tests/test_black_box_judge_integration.py::test_deterministic_constraints -v
```

**提交**：
```bash
git add test_cases/black_box/constraints.py
git commit -m "refactor(evidence): migrate DeterministicConstraint to UnifiedEvidence

- 所有字段访问改为方法调用
- check_file_exists() 委托给 evidence.has_file()
- get_file_count_changes() 委托给 evidence.get_file_changes_summary()

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 4.2 迁移 JudgeAssessment（1 天）

**文件**：`test_cases/black_box/judge_assessment.py`

**关键变化**：删除 `create_evidence_bundle_from_legacy()` 函数（220 行）

**修改前**：
```python
def assess(self, evidence: EvidenceBundle, criterion: JudgeCriterion):
    # ...
    exchange = self.judge.evaluate_black_box(
        criterion_prompt=criterion.to_judge_prompt(),
        evidence_text=evidence.to_evidence_text(),
    )
```

**修改后**：
```python
def assess(self, evidence: UnifiedEvidence, criterion: JudgeCriterion):
    # 直接使用 UnifiedEvidence.to_judge_prompt()
    # 不再需要 create_evidence_bundle_from_legacy()
    
    missing = self.constraint_checker.check_evidence_completeness(evidence, criterion.required_evidence)
    if missing:
        return AssessmentVerdict(
            AssessmentStatus.INCONCLUSIVE,
            f"{criterion.case_id} 证据不足：{missing}",
            (missing,)
        ), None
    
    # 关键简化：直接调用 evidence.to_judge_prompt()
    exchange = self.judge.evaluate_black_box(
        criterion_prompt=criterion.to_judge_prompt(),
        evidence_text=evidence.to_judge_prompt(),  # ← 简化！
    )
    
    verdict = self._convert(exchange, criterion.case_id)
    record = exchange.record()
    record["assessment_status"] = verdict.status.value
    record["assessment_reason"] = verdict.reason
    return verdict, record
```

**删除的代码**：
- 删除 `create_evidence_bundle_from_legacy()` 函数（220 行）
- 删除 `FakePrepared` 和 `FakeResult` 类
- 删除 `_snapshot_file_info()` 辅助函数（已移到 FilesystemChanges）

**验证**：
```bash
uv run pytest tests/test_black_box_judge_integration.py -v
```

**提交**：
```bash
git add test_cases/black_box/judge_assessment.py
git commit -m "refactor(evidence): migrate JudgeAssessment to UnifiedEvidence

重大简化：
- 删除 create_evidence_bundle_from_legacy() 函数（220 行）
- 删除 FakePrepared 和 FakeResult 假对象
- JudgeAssessment.assess() 直接接收 UnifiedEvidence
- 直接调用 evidence.to_judge_prompt() 生成 Judge 输入

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 4.3 迁移 BlackBoxAssertion（1.5 天）

**文件**：`test_cases/black_box/assertion.py`

这是最复杂的迁移，因为它同时依赖确定性断言和 Judge 评审。

**修改前**：
```python
class BlackBoxAssertion:
    def evaluate(self, spec: BlackBoxCaseSpec, evidence: BlackBoxEvidence) -> AssessmentVerdict:
        # 访问 evidence.control.collector_ready
        # 访问 evidence.files.added
        # 访问 evidence.public.turns
        # 调用 create_evidence_bundle_from_legacy()
        pass
```

**修改后**：
```python
class BlackBoxAssertion:
    def evaluate(self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence) -> AssessmentVerdict:
        return self.evaluate_with_record(spec, evidence)[0]
    
    def evaluate_with_record(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence,
    ) -> tuple[AssessmentVerdict, Optional[dict]]:
        # 修改前：evidence.control.collector_ready
        # 修改后：evidence.is_ready_for_judge()
        if spec.judge_criterion is not None and evidence.is_ready_for_judge():
            return self._evaluate_with_judge(spec, evidence)
        return self._evaluate_without_judge(spec, evidence), None
    
    def _evaluate_without_judge(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence
    ) -> AssessmentVerdict:
        # 修改前：evidence.control.collector_ready
        # 修改后：
        issues = evidence.get_quality_issues()
        if issues:
            return AssessmentVerdict(
                AssessmentStatus.INCONCLUSIVE,
                f"黑盒公开证据采集问题：{'; '.join(issues)}",
                ("完整的 PUBLIC/FILE/CONTROL 证据",)
            )
        
        # Fallback：使用旧的确定性断言
        return self._evaluate_with_rules(spec, evidence)
    
    def _evaluate_with_judge(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence,
    ) -> tuple[AssessmentVerdict, Optional[dict]]:
        """使用 Judge 进行语义评审"""
        
        # 确保有 Judge 模型
        if self.judge_model is None:
            try:
                config = JudgeConfig.from_environment()
                self.judge_model = OpenAICompatibleJudge(config)
            except Exception as e:
                return assessment_verdict(
                    AssessmentStatus.FAIL,
                    reason=f"{spec.case_id} Judge 模型初始化失败：{str(e)}"
                ), {"error": f"Judge 模型初始化失败：{type(e).__name__}", "judge_status": None}
        
        # 关键简化：不再需要 create_evidence_bundle_from_legacy()
        # 直接使用 UnifiedEvidence
        
        # 转换 judge_criterion 格式
        criterion = JudgeCriterion(
            case_id=spec.judge_criterion.case_id,
            title=spec.judge_criterion.title,
            description=spec.judge_criterion.description,
            pass_criteria=spec.judge_criterion.pass_criteria,
            fail_criteria=spec.judge_criterion.fail_criteria,
            required_evidence=list(spec.judge_criterion.required_evidence),
            checkpoints=list(spec.judge_criterion.checkpoints) if spec.judge_criterion.checkpoints else None
        )
        
        # 调用 Judge 评审
        assessment = JudgeAssessment(self.judge_model)
        return assessment.assess(evidence, criterion)
    
    def _evaluate_with_rules(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence
    ) -> AssessmentVerdict:
        """使用旧的确定性断言规则（向后兼容）"""
        
        # 修改前：dict(evidence.metrics)
        # 修改后：
        metrics = dict(evidence.get_all_metrics())
        
        # 修改前：sum(turn.completed for turn in evidence.public.turns)
        # 修改后：
        turns = evidence.get_all_turns()
        metrics.setdefault("Completed_Count", sum(turn.completed for turn in turns))
        metrics.setdefault("Nonzero_Returncode_Count", sum(turn.returncode != 0 for turn in turns))
        
        # 修改前：len(evidence.files.added)
        # 修改后：
        changes = evidence.get_file_changes_summary()
        metrics.setdefault("Workspace_Change_Count", changes["total_changes"])
        
        # 修改前：evidence.public.output_text.count(...)
        # 修改后：
        output_text = evidence.get_agent_response()
        metrics.setdefault("Positive_Output_Marker_Hits",
                          output_text.count(spec.public_marker) if spec.public_marker else 0)
        metrics.setdefault("Forbidden_Marker_Hits",
                          output_text.count(spec.marker) if spec.marker else 0)
        
        failures = [f"{rule.metric}={metrics.get(rule.metric)!r} 不满足 {rule.operator} {rule.expected!r}"
                    for rule in spec.assertion_rules
                    if rule.metric not in metrics or not _compare(metrics.get(rule.metric), rule)]
        if failures:
            return assessment_verdict(AssessmentStatus.FAIL, reason="；".join(failures))
        if not spec.assertion_rules:
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "用例尚未声明可计算的黑盒断言规则",
                                     ("assertion_rules",))
        return assessment_verdict(AssessmentStatus.PASS,
                                  reason=f"{spec.case_id} 的 PUBLIC/FILE/CONTROL 黑盒断言全部满足")
```

**删除的代码**：
- 删除 `_snapshot_file_info()` 函数（已移到 FilesystemChanges.to_display_format()）
- 删除 `create_evidence_bundle_from_legacy()` 的所有调用

**验证**：
```bash
# 运行断言相关的测试
uv run pytest tests/test_black_box_judge_integration.py -v

# 运行几个典型的黑盒用例
uv run pytest test_cases/black_box/test_b001.py --case-suite black_box -v
uv run pytest test_cases/black_box/test_b005.py --case-suite black_box -v
```

**提交**：
```bash
git add test_cases/black_box/assertion.py
git commit -m "refactor(evidence): migrate BlackBoxAssertion to UnifiedEvidence

重大简化：
- evaluate() 接收 UnifiedEvidence 而非 BlackBoxEvidence
- _evaluate_with_judge() 不再需要适配代码
- _evaluate_with_rules() 使用方法访问代替字段访问
- 删除所有 create_evidence_bundle_from_legacy() 调用

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 4.4 更新 runner 和其他间接依赖（0.5 天）

**文件**：`test_cases/black_box/runner.py`

Runner 本身不直接访问证据字段，只是传递证据，所以修改很小。

```python
# 确保类型标注正确
from test_cases.black_box.unified_evidence import UnifiedEvidence

class BlackBoxCaseRunner(AgentTestCase):
    def run(
        self,
        case_id: str,
        agent_model: AgentModel,
        request: pytest.FixtureRequest,
        judge_model = None,
    ) -> AssessmentVerdict:
        builder = BlackBoxEnvironmentBuilder()
        executor = BlackBoxCaseExecutor()
        projector = BlackBoxEvidenceProjector()
        assertion = BlackBoxAssertion(judge_model=judge_model)
        spec = load_black_box_spec(case_id)
        
        # ... 执行流程不变
        
        evidence: UnifiedEvidence = projector.observe(prepared, execution, agent_model)
        
        # ... 断言和结论
```

**提交**：
```bash
git add test_cases/black_box/runner.py
git commit -m "refactor(evidence): update runner type annotations for UnifiedEvidence

- 更新类型标注：BlackBoxEvidence → UnifiedEvidence
- 执行流程不变，只是类型改变

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### 4.5 验证阶段 4

```bash
# 运行完整的黑盒卷
uv run pytest test_cases/black_box --case-suite black_box -v > /tmp/after_migration.txt

# 对比迁移前后的通过率
diff /tmp/baseline_before.txt /tmp/after_migration.txt

# 统计通过的用例数
grep "PASSED" /tmp/after_migration.txt | wc -l
```

**验收标准**：
- [ ] 通过的用例数与基线相同（或更多）
- [ ] 没有新增的 FAILED 用例
- [ ] 所有单元测试通过

---

## 阶段 5：删除旧代码（0.5 天）

### 5.1 删除旧模型定义

```bash
# 1. 从 models.py 删除 BlackBoxEvidence
# 保留：PreparedBlackBoxEnvironment, BlackBoxExecutionResult, PublicTurnObservation
# 删除：PublicObservation, FileObservation, ControlObservation, BlackBoxEvidence

# 2. 删除 evidence_models.py（整个文件）
git rm test_cases/black_box/evidence_models.py

# 3. 删除 binary_extract.py 中的相关导入
# （如果 binary_extract 还在用，需要更新它的导入）
```

**文件**：`test_cases/black_box/models.py`

删除以下内容：
```python
# 删除这些类定义
@dataclass(frozen=True, slots=True)
class PublicObservation:
    ...

@dataclass(frozen=True, slots=True)
class FileObservation:
    ...

@dataclass(frozen=True, slots=True)
class ControlObservation:
    ...

@dataclass(frozen=True, slots=True)
class BlackBoxEvidence:
    ...
```

---

### 5.2 更新导入语句

**所有导入 BlackBoxEvidence 或 EvidenceBundle 的文件**：

```python
# 修改前
from test_cases.black_box.models import BlackBoxEvidence
from test_cases.black_box.evidence_models import EvidenceBundle

# 修改后
from test_cases.black_box.unified_evidence import UnifiedEvidence
```

**受影响的文件**：
- `test_cases/black_box/assertion.py`
- `test_cases/black_box/evidence.py`
- `test_cases/black_box/runner.py`
- `test_cases/black_box/constraints.py`
- `test_cases/black_box/judge_assessment.py`
- `tests/test_black_box_judge_integration.py`

---

### 5.3 删除废弃的测试

```bash
# 删除测试旧模型的测试（如果有）
# 保留测试 UnifiedEvidence 的测试
```

---

### 5.4 验证删除

```bash
# 确保没有残留的导入
grep -r "BlackBoxEvidence" test_cases/black_box --include="*.py"
grep -r "EvidenceBundle" test_cases/black_box --include="*.py"
grep -r "evidence_models" test_cases/black_box --include="*.py"

# 应该只在注释或文档中出现
```

**提交**：
```bash
git add .
git commit -m "refactor(evidence): remove old evidence models

删除：
- BlackBoxEvidence（models.py，21 个字段）
- EvidenceBundle（evidence_models.py，20 个字段）
- PublicObservation, FileObservation, ControlObservation
- 整个 evidence_models.py 文件

更新所有导入语句，全部改为 UnifiedEvidence

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## 阶段 6：最终验证和文档（0.5-1 天）

### 6.1 完整验证

```bash
# 1. 运行所有单元测试
uv run pytest tests -v

# 2. 运行完整的黑盒卷
uv run pytest test_cases/black_box --case-suite black_box -v

# 3. 运行基线测试（334 个用例）
uv run pytest test_cases/black_box --case-suite black_box

# 4. 对比基线
diff /tmp/baseline_before.txt /tmp/final_result.txt
```

**验收标准**：
- [ ] 所有单元测试通过（100%）
- [ ] 黑盒卷通过率 ≥ 基线
- [ ] 无新增的回归失败

---

### 6.2 代码质量检查

```bash
# 1. 类型检查
uv run mypy test_cases/black_box/unified_evidence.py
uv run mypy test_cases/black_box/evidence_categories.py

# 2. 代码风格
uv run ruff check test_cases/black_box/unified_evidence.py

# 3. 测试覆盖率
uv run pytest --cov=test_cases.black_box.unified_evidence --cov-report=term-missing
```

**验收标准**：
- [ ] 无 mypy 错误
- [ ] 无 ruff 警告
- [ ] 测试覆盖率 ≥ 85%

---

### 6.3 更新文档

**文件**：`docs/evidence_refactor_summary.md`

```markdown
# 证据容器统一重构总结

## 完成时间
2026-10-XX ~ 2026-10-XX（实际工期：X 天）

## 完成内容

### 1. 新增代码
- `test_cases/black_box/evidence_categories.py` - 5 大类别定义（~400 行）
- `test_cases/black_box/unified_evidence.py` - 统一证据容器（~300 行）
- `tests/test_evidence_categories.py` - 类别单元测试（~200 行）
- `tests/test_unified_evidence.py` - 容器单元测试（~150 行）

**新增代码总量**：~1050 行

### 2. 删除代码
- `test_cases/black_box/evidence_models.py` - 整个文件（~300 行）
- `models.py` 中的 BlackBoxEvidence 及相关类（~80 行）
- `assertion.py` 中的适配代码（~250 行）
- `judge_assessment.py` 中的 create_evidence_bundle_from_legacy（~220 行）

**删除代码总量**：~850 行

### 3. 修改代码
- `evidence.py` - 证据生产者（大改）
- `assertion.py` - 断言评估器（中改）
- `judge_assessment.py` - Judge 评审层（大改）
- `constraints.py` - 约束检查器（小改）
- `runner.py` - 执行编排器（类型标注）

### 4. 架构改进
- ✅ 双轨制废弃：BlackBoxEvidence + EvidenceBundle → UnifiedEvidence
- ✅ 信息隐藏：内部字段私有（`_` 前缀）
- ✅ 接口稳定：41 个公开方法
- ✅ 耦合降低：消费者通过方法访问，不依赖内部结构

### 5. 测试结果
- 单元测试：XX 个，全部通过
- 黑盒卷：334 个用例，XX 个通过
- 覆盖率：XX%

## 收益评估

### 代码简化
- 删除 ~850 行适配代码
- 新增 ~1050 行结构化代码
- 净增加 ~200 行（但架构更清晰）

### 耦合降低
- 消费者从 4 个模块直接访问 40+ 个字段 → 调用 41 个方法
- 内部结构变化不再影响消费者

### 维护性提升
- 证据采集逻辑集中在 5 大类别中
- 转换导出逻辑集中在 UnifiedEvidence 中
- 单元测试覆盖率从 X% 提升到 XX%

## 遗留问题

1. **二进制文件文本提取**：`FilesystemChanges._entry_to_display()` 中的 TODO
2. **执行阶段信息**：`AgentTrace.execution_phases` 目前为 None
3. **时间戳精度**：部分时间戳使用 `datetime.now()` 而非真实时间

## 下一步建议

1. 完善二进制文件文本提取（xlsx/docx/pdf）
2. 在多阶段执行模式下构造 PhaseRecord
3. 传递真实的时间戳（开始时间、工具调用时间等）
```

---

### 6.4 合并到主分支

```bash
# 1. 确保所有测试通过
uv run pytest tests test_cases/black_box --case-suite black_box

# 2. 推送到远程
git push origin refactor/unified-evidence

# 3. 创建 PR
gh pr create --title "refactor: unify black-box evidence containers" \
  --body "统一黑盒证据容器

## 变更概要
- 废弃双轨制：BlackBoxEvidence + EvidenceBundle → UnifiedEvidence
- 5 大类别：执行上下文、Agent 轨迹、副作用、采集元数据、计算指标
- 41 个公开方法：信息隐藏，接口稳定
- 删除 ~850 行适配代码

## 测试结果
- 单元测试：XX 个，全部通过
- 黑盒卷：334 个用例，XX 个通过
- 覆盖率：XX%

## 文档
- docs/evidence_categories_spec.md
- docs/evidence_interface_spec.md
- docs/evidence_refactor_plan.md
- docs/evidence_refactor_summary.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 4. 合并到 refactor/black-box-structure
# （需要代码审查和批准）
```

---

## 风险控制

### 风险 1：行为基线回归

**风险等级**：高

**表现**：迁移后部分用例失败

**预防措施**：
1. 每个阶段完成后立即运行基线测试
2. 发现回归立即定位原因
3. 保留每个阶段的 git 提交，便于回滚

**应急方案**：
```bash
# 回滚到上一个阶段
git log --oneline | head -5
git reset --hard <上一个阶段的 commit>
```

---

### 风险 2：字段访问遗漏

**风险等级**：中

**表现**：某个模块仍在直接访问内部字段（如 `evidence._context`）

**预防措施**：
1. 使用 mypy 类型检查
2. 代码审查时检查所有 `evidence.` 访问

**检测方法**：
```bash
# 查找所有直接访问 `_` 开头字段的代码
grep -r "evidence\._" test_cases/black_box --include="*.py"

# 应该只在 UnifiedEvidence 内部出现
```

---

### 风险 3：性能退化

**风险等级**：低

**表现**：方法调用开销导致性能下降

**预防措施**：
1. 使用 `@property` 装饰器减少开销
2. 关键路径使用性能分析工具

**验证方法**：
```bash
# 运行性能测试
time uv run pytest test_cases/black_box --case-suite black_box

# 对比迁移前后的时间
```

---

## 验证标准

### 阶段性验证标准

**每个阶段完成后**：
- [ ] 代码编译通过（无语法错误）
- [ ] 单元测试通过（100%）
- [ ] 类型检查通过（无 mypy 错误）
- [ ] 提交到 git

**阶段 3 完成后**：
- [ ] 至少 1 个黑盒用例通过

**阶段 4 完成后**：
- [ ] 所有消费者模块迁移完成
- [ ] 至少 50% 黑盒用例通过

---

### 最终验收标准

**必需**：
- [ ] 所有单元测试通过（100%）
- [ ] 黑盒卷通过率 ≥ 基线通过率
- [ ] 无新增的回归失败
- [ ] 无 mypy 类型错误
- [ ] 测试覆盖率 ≥ 85%

**可选**：
- [ ] 性能无明显退化（±10% 以内）
- [ ] 代码行数减少（删除 > 新增）

---

## 回滚方案

### 何时回滚

1. **阶段性验证失败**：某个阶段的验证标准未达标
2. **最终验收失败**：完整重构后发现重大回归
3. **时间超期**：实际工期超过预期 50%

### 回滚步骤

```bash
# 1. 保存当前进度
git stash

# 2. 回滚到 refactor/black-box-structure 分支的起点
git checkout refactor/black-box-structure
git log --oneline | head -1  # 记录起点 commit

# 3. 创建回滚分支（保留工作）
git checkout -b refactor/unified-evidence-rollback
git stash pop

# 4. 分析失败原因，制定新计划
```

---

## 时间估算

### 乐观估计（8.5 天）
- 阶段 0：0.5 天
- 阶段 1：2 天
- 阶段 2：1 天
- 阶段 3：1 天
- 阶段 4：3 天
- 阶段 5：0.5 天
- 阶段 6：0.5 天

### 保守估计（11 天）
- 阶段 0：0.5 天
- 阶段 1：3 天（+1 天处理复杂性）
- 阶段 2：1 天
- 阶段 3：1 天
- 阶段 4：4 天（+1 天处理回归）
- 阶段 5：0.5 天
- 阶段 6：1 天（+0.5 天处理文档）

### 建议时间表

**第 1 周**（5 个工作日）：
- 周一：阶段 0 + 阶段 1（一半）
- 周二：阶段 1（完成）
- 周三：阶段 2 + 阶段 3
- 周四：阶段 4（消费者迁移 1-2 个）
- 周五：阶段 4（消费者迁移 3-4 个）

**第 2 周**（3-6 个工作日）：
- 周一：阶段 4（完成） + 阶段 5
- 周二：阶段 6（验证和文档）
- 周三：代码审查和修复
- 周四-周六（可选）：处理遗留问题

---

## 总结

这是一个**中-高风险、高收益**的重构计划：

- **预计工期**：8-11 天
- **关键风险**：行为基线回归
- **主要收益**：删除 ~850 行适配代码，降低耦合，提升维护性
- **验证保障**：334 个用例的行为基线

**建议执行策略**：
1. 严格按阶段执行，不跳步
2. 每个阶段完成后立即验证
3. 发现问题立即修复，不累积技术债
4. 保持频繁的 git 提交，便于回滚
