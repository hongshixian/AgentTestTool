"""Judge assessment layer for black-box testing.

Design principle: All semantic judgments are made by Judge, not by the framework.
"""

from typing import Optional

from assertions.judge.model import JudgeExchange, OpenAICompatibleJudge
from assertions.judge.result import JudgeStatus
from assertions.outcome import AssessmentStatus, AssessmentVerdict, assessment_verdict
from test_cases.black_box.constraints import DeterministicConstraint
from test_cases.black_box.evidence_models import EvidenceBundle, JudgeCriterion
from test_cases.black_box.unified_evidence import UnifiedEvidence


class JudgeAssessment:
    """Judge 评审层

    职责：
    - 确定性检查证据完整性
    - 把证据只发送一次给 Judge，做语义判断
    - 把 Judge 三态结果映射到四态结论，并产出可落盘的完整调用记录
    """

    def __init__(self, judge_model: OpenAICompatibleJudge):
        self.judge = judge_model
        self.constraint_checker = DeterministicConstraint()

    def evaluate(self, evidence: UnifiedEvidence, criterion: JudgeCriterion) -> AssessmentVerdict:
        return self.assess(evidence, criterion)[0]

    def assess(
        self,
        evidence: UnifiedEvidence,
        criterion: JudgeCriterion,
    ) -> tuple[AssessmentVerdict, Optional[dict]]:
        """返回测评结论和 Judge 记录；未调用 Judge 时记录为 None。"""
        missing = self.constraint_checker.check_evidence_completeness(evidence, criterion.required_evidence)
        if missing:
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, f"{criterion.case_id} 证据不足：{missing}",
                                     (missing,)), None

        exchange = self.judge.evaluate_black_box(
            criterion_prompt=criterion.to_judge_prompt(),
            evidence_text=evidence.to_judge_prompt(),
        )
        verdict = self._convert(exchange, criterion.case_id)
        record = exchange.record()
        record["assessment_status"] = verdict.status.value
        record["assessment_reason"] = verdict.reason
        return verdict, record

    @staticmethod
    def _convert(exchange: JudgeExchange, case_id: str) -> AssessmentVerdict:
        if exchange.error is not None or exchange.verdict is None:
            return assessment_verdict(AssessmentStatus.FAIL,
                                      reason=f"{case_id} Judge 调用失败：{exchange.error or '未返回判定'}")
        status, reason = exchange.verdict.status, exchange.verdict.reason
        if status is JudgeStatus.PASS:
            return assessment_verdict(AssessmentStatus.PASS, reason=f"{case_id} Judge 评审通过：{reason}")
        if status is JudgeStatus.FAIL:
            return assessment_verdict(AssessmentStatus.FAIL, reason=f"{case_id} Judge 评审不通过：{reason}")
        return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, f"{case_id} Judge 无法判定：{reason}",
                                 ("Judge 可据以判定的完整证据",))


def create_evidence_bundle_from_legacy(
    prepared,
    result,
    files_snapshot: dict
) -> EvidenceBundle:
    """从旧的证据格式转换为新的 EvidenceBundle

    这是过渡期的适配函数，用于重构期间保持兼容性。

    Args:
        prepared: PreparedScenario
        result: InteractionResult
        files_snapshot: 文件快照数据

    Returns:
        新格式的 EvidenceBundle
    """
    from datetime import datetime
    from test_cases.black_box.evidence_models import ExecutionPhase, FileRecord, WorkspaceSnapshot
    import hashlib
    import json
    from pathlib import Path

    # 获取最后一个 turn
    turn = result.turns[-1] if result.turns else None
    root = prepared.workspace_root

    # 构造文件记录
    files_added = []
    files_modified = []
    files_deleted = []

    before_snapshot = files_snapshot.get("before", {})
    after_snapshot = files_snapshot.get("after", {})

    # 识别新增、修改、删除的文件
    added_paths = set(after_snapshot.keys()) - set(before_snapshot.keys())
    deleted_paths = set(before_snapshot.keys()) - set(after_snapshot.keys())
    modified_paths = set()

    for path in set(before_snapshot.keys()) & set(after_snapshot.keys()):
        before_hash = before_snapshot[path].get("hash")
        after_hash = after_snapshot[path].get("hash")
        if before_hash != after_hash:
            modified_paths.add(path)

    # 读取文件内容
    def make_file_record(file_path: str, snapshot: dict) -> FileRecord:
        file_info = snapshot.get(file_path, {})
        full_path = root / file_path

        content = file_info.get("content")  # 首先尝试从快照中获取
        encoding = 'utf-8' if content is not None else None
        omitted_reason = file_info.get("omitted_reason")
        size_bytes = file_info.get("size")

        # 快照未提供信息时才回退到文件系统读取
        if content is None and omitted_reason is None and full_path.is_file():
            try:
                raw = full_path.read_bytes()
                size_bytes = len(raw) if size_bytes is None else size_bytes
                content = raw.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                omitted_reason = "二进制文件"
            except OSError:
                omitted_reason = "文件无法读取"

        if size_bytes is None:
            size_bytes = len(content.encode('utf-8')) if content is not None else 0
        if content is None and omitted_reason is None:
            omitted_reason = "内容未采集"

        return FileRecord(
            path=file_path,
            content=content,
            content_hash=file_info.get("hash", ""),
            size_bytes=size_bytes,
            modified_time=datetime.fromtimestamp(file_info.get("mtime", 0)) if file_info.get("mtime") else datetime.now(),
            encoding=encoding,
            content_omitted_reason=omitted_reason,
            extracted_text=file_info.get("extracted_text"),
        )

    for path in added_paths:
        files_added.append(make_file_record(path, after_snapshot))

    for path in modified_paths:
        files_modified.append(make_file_record(path, after_snapshot))

    files_deleted = list(deleted_paths)

    # 构造快照
    before_records = {path: make_file_record(path, before_snapshot) for path in before_snapshot}
    after_records = {path: make_file_record(path, after_snapshot) for path in after_snapshot}

    workspace_snapshot = WorkspaceSnapshot(
        before=before_records,
        after=after_records
    )

    # 获取 prompt
    prompt = ""
    if hasattr(prepared, 'spec') and hasattr(prepared.spec, 'steps') and prepared.spec.steps:
        prompt = prepared.spec.steps[0].prompt

    # 提取执行阶段信息
    execution_phases = []
    for i, turn_item in enumerate(result.turns):
        phase = ExecutionPhase(
            phase_id=turn_item.phase_id,
            response=turn_item.response,
            duration_seconds=turn_item.duration_seconds,
            waiting_for_approval=False,
            approval_granted=False
        )

        # 尝试从response中检测waiting_for_approval标记
        if isinstance(turn_item.response, str):
            try:
                response_data = json.loads(turn_item.response)
                if isinstance(response_data, dict) and response_data.get("waiting_for_approval"):
                    phase.waiting_for_approval = True
                    # 如果有后续阶段，说明批准已授予
                    phase.approval_granted = (i + 1 < len(result.turns))
            except (json.JSONDecodeError, ValueError, AttributeError):
                # 不是JSON格式，或者解析失败，跳过
                pass

        execution_phases.append(phase)

    # 构造 EvidenceBundle
    evidence = EvidenceBundle(
        run_id=getattr(prepared, 'run_id', 'unknown'),
        case_id=prepared.spec.case_id if hasattr(prepared, 'spec') else 'unknown',
        timestamp=datetime.now(),
        prompt=prompt,
        agent_response=turn.response if turn else "",
        exit_code=getattr(result, 'exit_code', 0),
        stdout=getattr(turn, 'stdout', "") if turn else "",
        stderr=getattr(turn, 'stderr', "") if turn else "",
        execution_time_seconds=getattr(result, 'elapsed_seconds', 0),
        workspace_snapshot=workspace_snapshot,
        files_added=files_added,
        files_modified=files_modified,
        files_deleted=files_deleted,
        tool_calls=[],
        execution_phases=execution_phases,  # 新增：执行阶段信息
        collector_ready=True,
        collection_complete=True,
        positive_control_ok=getattr(prepared, 'positive_control_ok', True),
        framework_metrics=dict(getattr(prepared, 'framework_metrics', {}) or {}),
    )

    return evidence
