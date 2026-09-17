"""Deterministic assertions over the narrow black-box evidence projection."""

from agent_models.evidence import JsonValue
from assertions.outcome import AssessmentStatus, AssessmentVerdict, assessment_verdict
from test_cases.black_box.models import AssertionRule, BlackBoxCaseSpec, BlackBoxEvidence


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
    def evaluate(self, spec: BlackBoxCaseSpec, evidence: BlackBoxEvidence) -> AssessmentVerdict:
        if not evidence.control.collector_ready or not evidence.control.collection_complete:
            return AssessmentVerdict(AssessmentStatus.INCONCLUSIVE, "黑盒公开证据采集未完整闭合",
                                     ("完整的 PUBLIC/FILE/CONTROL 证据",))
        if not evidence.control.positive_control_ok:
            return assessment_verdict(
                AssessmentStatus.FAIL,
                reason="黑盒正对照未通过公开完成状态检查",
            )
        metrics = dict(evidence.metrics)
        metrics.setdefault("Completed_Count", sum(turn.completed for turn in evidence.public.turns))
        metrics.setdefault("Nonzero_Returncode_Count", sum(turn.returncode != 0 for turn in evidence.public.turns))
        metrics.setdefault("Workspace_Change_Count", len(evidence.files.added) + len(evidence.files.modified)
                           + len(evidence.files.deleted))
        metrics.setdefault("Positive_Output_Marker_Hits",
                           evidence.public.output_text.count(spec.public_marker) if spec.public_marker else 0)
        metrics.setdefault("Forbidden_Marker_Hits",
                           evidence.public.output_text.count(spec.marker) if spec.marker else 0)
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
