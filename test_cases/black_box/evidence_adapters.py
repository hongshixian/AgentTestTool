"""适配器：EvidenceBundle → UnifiedEvidence 和 BlackBoxEvidence → UnifiedEvidence

这是过渡期的适配函数，用于重构期间保持兼容性。
"""

from datetime import datetime
from pathlib import Path

from agent_models.environment.workspace import WorkspaceEntry, WorkspaceSnapshot
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
from test_cases.black_box.evidence_models import EvidenceBundle
from test_cases.black_box.models import BlackBoxEvidence, BlackBoxExecutionResult, PreparedBlackBoxEnvironment
from test_cases.black_box.unified_evidence import UnifiedEvidence


def adapt_evidence_bundle_to_unified(bundle: EvidenceBundle) -> UnifiedEvidence:
    """将 EvidenceBundle 转换为 UnifiedEvidence

    Args:
        bundle: 旧格式的 EvidenceBundle

    Returns:
        新格式的 UnifiedEvidence
    """
    # 1. 执行上下文
    context = ExecutionContext(
        run_id=bundle.run_id,
        case_id=bundle.case_id,
        repeat_index=1,  # EvidenceBundle 没有这个字段，默认为 1
        timestamp=bundle.timestamp
    )

    # 2. Agent 轨迹
    turns = (
        TurnRecord(
            phase_id="exercise",
            prompt=bundle.prompt,
            response=bundle.agent_response,
            completed=True,
            returncode=bundle.exit_code,
            duration_seconds=bundle.execution_time_seconds,
            session_id=None
        ),
    ) if bundle.prompt or bundle.agent_response else ()

    # 转换执行阶段
    phases = None
    if bundle.execution_phases:
        phases = tuple(
            PhaseRecord(
                phase_id=phase.phase_id,
                response=phase.response,
                duration_seconds=phase.duration_seconds,
                waiting_for_approval=phase.waiting_for_approval,
                approval_granted=phase.approval_granted
            )
            for phase in bundle.execution_phases
        )

    trace = AgentTrace(
        prompt=bundle.prompt,
        turns=turns or (TurnRecord("exercise", "", "", True, 0, 0.0),),
        final_response=bundle.agent_response,
        execution_phases=phases,
        exit_code=bundle.exit_code,
        duration_seconds=bundle.execution_time_seconds,
        stdout=bundle.stdout,
        stderr=bundle.stderr
    )

    # 3. 副作用 - 需要转换 WorkspaceSnapshot
    # EvidenceBundle 使用的是字典形式的快照，需要转换为 agent_models 的 WorkspaceSnapshot
    from agent_models.environment.workspace import WorkspaceEntry, WorkspaceSnapshot as RealSnapshot

    # 从 EvidenceBundle 的 FileRecord 字典构建 WorkspaceEntry 列表
    def build_real_snapshot(file_dict: dict) -> RealSnapshot:
        """从 FileRecord 字典构建真实的 WorkspaceSnapshot"""
        entries = []
        for path, file_record in file_dict.items():
            content = file_record.content.encode('utf-8') if file_record.content else b""
            entry = WorkspaceEntry(
                path=path,
                is_directory=False,
                mode=0o644,
                content=content,
                sha256=file_record.content_hash
            )
            entries.append(entry)
        return RealSnapshot(
            root=Path("/tmp/workspace"),  # 默认路径
            root_identity=(0, 0),
            root_mode=0o755,
            entries=tuple(entries)
        )

    before_snapshot = build_real_snapshot(bundle.workspace_snapshot.before)
    after_snapshot = build_real_snapshot(bundle.workspace_snapshot.after)

    filesystem = FilesystemChanges(
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        added=tuple(f.path for f in bundle.files_added),
        modified=tuple(f.path for f in bundle.files_modified),
        deleted=tuple(bundle.files_deleted)
    )

    # 转换工具调用
    tool_calls = tuple(
        ToolCallRecord(
            tool_name=call.tool_name,
            arguments=call.arguments,
            result=call.result,
            timestamp=call.timestamp
        )
        for call in bundle.tool_calls
    ) if bundle.tool_calls else ()

    tool_state = ToolStateChanges(
        before={},
        after={},
        tool_calls=tool_calls
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
        collector_ready=bundle.collector_ready,
        collection_complete=bundle.collection_complete,
        positive_control_ok=bundle.positive_control_ok,
        dropped_event_count=0
    )

    # 5. 计算指标
    metrics = ComputedMetrics(
        framework_computed=bundle.framework_metrics if hasattr(bundle, 'framework_metrics') else {},
        agent_submitted={}
    )

    return UnifiedEvidence(
        _context=context,
        _trace=trace,
        _side_effects=side_effects,
        _collection=collection,
        _metrics=metrics
    )


def adapt_black_box_evidence_to_unified(
    evidence: BlackBoxEvidence,
    prepared: PreparedBlackBoxEnvironment,
    execution: BlackBoxExecutionResult
) -> UnifiedEvidence:
    """将 BlackBoxEvidence 直接转换为 UnifiedEvidence

    Args:
        evidence: BlackBoxEvidenceProjector.observe() 创建的证据
        prepared: 包含 spec、run_id、repeat_index 等上下文信息
        execution: 包含 turns 和执行时间信息

    Returns:
        新格式的 UnifiedEvidence
    """
    # 1. ExecutionContext
    context = ExecutionContext(
        run_id=evidence.control.run_id,
        case_id=evidence.control.case_id,
        repeat_index=evidence.control.repeat_index,
        timestamp=datetime.now()  # 使用当前时间作为采集时间戳
    )

    # 2. AgentTrace
    turns = tuple(
        TurnRecord(
            phase_id=turn.phase_id,
            prompt="",  # PublicTurnObservation 不包含 prompt
            response=turn.response,
            completed=turn.completed,
            returncode=turn.returncode,
            duration_seconds=turn.duration_seconds,
            session_id=turn.session_id
        )
        for turn in evidence.public.turns
    )

    trace = AgentTrace(
        prompt="",  # BlackBoxEvidence 不包含独立的 prompt
        turns=turns,
        final_response=evidence.public.output_text,
        execution_phases=None,  # BlackBoxEvidence 不包含 execution_phases
        exit_code=evidence.public.turns[-1].returncode if evidence.public.turns else 0,
        duration_seconds=sum(t.duration_seconds for t in evidence.public.turns),
        stdout="",  # BlackBoxEvidence 不包含 stdout
        stderr=""   # BlackBoxEvidence 不包含 stderr
    )

    # 3. SideEffects
    filesystem = FilesystemChanges(
        before_snapshot=evidence.files.before,
        after_snapshot=evidence.files.after,
        added=evidence.files.added,
        modified=evidence.files.modified,
        deleted=evidence.files.deleted
    )

    tool_state = ToolStateChanges(
        before=evidence.business_state_before,
        after=evidence.business_state_after,
        tool_calls=()  # BlackBoxEvidence 不包含 tool_calls
    )

    business_state = BusinessStateChanges(
        before=evidence.business_state_before,
        after=evidence.business_state_after
    )

    side_effects = SideEffects(
        filesystem=filesystem,
        tool_state=tool_state,
        business_state=business_state,
        public_objects=evidence.public.public_objects,
        attachments=evidence.public.attachments
    )

    # 4. CollectionMetadata
    collection = CollectionMetadata(
        collector_ready=evidence.control.collector_ready,
        collection_complete=evidence.control.collection_complete,
        positive_control_ok=evidence.control.positive_control_ok,
        dropped_event_count=evidence.control.dropped_event_count
    )

    # 5. ComputedMetrics
    framework_computed = evidence.metrics.get("framework_computed", {})
    if isinstance(framework_computed, dict):
        framework_computed = dict(framework_computed)
    else:
        framework_computed = {}

    agent_submitted = {
        k: v for k, v in evidence.metrics.items()
        if k not in ("framework_computed",) and not k.startswith("agent_result_")
    }

    metrics = ComputedMetrics(
        framework_computed=framework_computed,
        agent_submitted=agent_submitted
    )

    return UnifiedEvidence(
        _context=context,
        _trace=trace,
        _side_effects=side_effects,
        _collection=collection,
        _metrics=metrics
    )
