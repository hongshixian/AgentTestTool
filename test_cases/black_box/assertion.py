"""Deterministic assertions over the narrow black-box evidence projection."""

from typing import Optional

from agent_models.evidence import JsonValue
from assertions.judge.model import JudgeConfig, OpenAICompatibleJudge
from assertions.outcome import AssessmentStatus, AssessmentVerdict, assessment_verdict
from test_cases.black_box.models import AssertionRule, BlackBoxCaseSpec
from test_cases.black_box.unified_evidence import UnifiedEvidence
from test_cases.black_box.binary_extract import extract_text, supported
from test_cases.black_box.evidence_models import JudgeCriterion


def _snapshot_file_info(entry, *, extract: bool = False) -> dict:
    """Describe one snapshot file for Judge: real size always, text when decodable.

    For changed binary deliverables (``extract=True``) xlsx/docx/pdf text is
    extracted in a bounded, format-only way so Judge can read what was written.
    """
    raw = entry.content or b""
    info = {"hash": entry.sha256, "size": len(raw), "mtime": 0, "content": None,
            "omitted_reason": None, "extracted_text": None}
    if not raw:
        info["content"] = ""
        return info
    try:
        info["content"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        info["omitted_reason"] = "二进制文件"
        if extract and supported(entry.path):
            extraction = extract_text(entry.path, raw)
            if extraction.text is not None:
                info["extracted_text"] = extraction.text
            else:
                info["omitted_reason"] = f"二进制文件；{extraction.reason}"
    return info


def _compare(actual: JsonValue, rule: AssertionRule) -> bool:
    expected = rule.expected
    operations = {"eq": lambda: actual == expected, "ne": lambda: actual != expected,
                  "lt": lambda: actual < expected, "le": lambda: actual <= expected,
                  "gt": lambda: actual > expected, "ge": lambda: actual >= expected,
                  "contains": lambda: expected in actual, "not_contains": lambda: expected not in actual}
    try:
        return bool(operations[rule.operator]())
    except (TypeError, KeyError):
        return False


class BlackBoxAssertion:
    """黑盒断言评估

    设计原则：
    - 优先使用 Judge 评审（如果 spec 有 judge_criterion）
    - Fallback 到旧的确定性断言（用于向后兼容）
    """

    def __init__(self, judge_model: Optional[OpenAICompatibleJudge] = None):
        self.judge_model = judge_model

    def evaluate(self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence) -> AssessmentVerdict:
        return self.evaluate_with_record(spec, evidence)[0]

    def evaluate_with_record(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence,
    ) -> tuple[AssessmentVerdict, Optional[dict]]:
        """返回结论和 Judge 调用记录；断言拿不到台账，记录交给 runner 落盘。"""
        if spec.judge_criterion is not None and evidence.is_collector_ready() \
                and evidence.is_collection_complete() and evidence.is_positive_control_ok():
            return self._evaluate_with_judge(spec, evidence)
        return self._evaluate_without_judge(spec, evidence), None

    def _evaluate_without_judge(self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence) -> AssessmentVerdict:
        # 检查证据完整性（确定性检查）
        if not evidence.is_collector_ready() or not evidence.is_collection_complete():
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "黑盒公开证据采集未完整闭合",
                                     ("完整的 PUBLIC/FILE/CONTROL 证据",))
        if not evidence.is_positive_control_ok():
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason="黑盒正对照未通过公开完成状态检查",
            )

        # Fallback：使用旧的确定性断言（向后兼容）
        return self._evaluate_with_rules(spec, evidence)

    def _evaluate_with_judge(
        self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence,
    ) -> tuple[AssessmentVerdict, Optional[dict]]:
        """使用 Judge 进行语义评审"""
        from test_cases.black_box.judge_assessment import JudgeAssessment

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

        # UnifiedEvidence 已经是正确格式，直接使用
        try:
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
        except Exception as e:
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason=f"{spec.case_id} Judge 评审失败：{str(e)}"
            ), {"error": f"Judge 评审失败：{type(e).__name__}: {e}", "judge_status": None}

    def _evaluate_with_rules(self, spec: BlackBoxCaseSpec, evidence: UnifiedEvidence) -> AssessmentVerdict:
        """使用旧的确定性断言规则（向后兼容）"""
        metrics = dict(evidence.get_all_metrics())
        all_turns = evidence.get_all_turns()
        metrics.setdefault("Completed_Count", sum(turn.completed for turn in all_turns))
        metrics.setdefault("Nonzero_Returncode_Count", sum(turn.returncode != 0 for turn in all_turns))
        files_summary = evidence.get_file_changes_summary()
        metrics.setdefault("Workspace_Change_Count",
                           len(files_summary['added']) + len(files_summary['modified']) + len(files_summary['deleted']))
        agent_response = evidence.get_agent_response()
        metrics.setdefault("Positive_Output_Marker_Hits",
                           agent_response.count(spec.public_marker) if spec.public_marker else 0)
        metrics.setdefault("Forbidden_Marker_Hits",
                           agent_response.count(spec.marker) if spec.marker else 0)

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
