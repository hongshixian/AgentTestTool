"""Project public output and explicit side effects into black-box evidence."""

from agent_models import AgentModel
from test_cases.black_box.models import (BlackBoxEvidence, BlackBoxExecutionResult, ControlObservation,
                                         FileObservation, PreparedBlackBoxEnvironment, PublicObservation)


class BlackBoxEvidenceProjector:
    def observe(self, prepared: PreparedBlackBoxEnvironment, execution: BlackBoxExecutionResult,
                agent_model: AgentModel) -> BlackBoxEvidence:
        environment = agent_model.environment
        before = prepared.baseline.workspace
        after = environment.workspace.snapshot()
        difference = environment.workspace.diff(before)
        runtime = environment.runtime
        health = environment.health()
        positive_control_ok = bool(execution.turns) and execution.turns[0].completed and execution.turns[0].returncode == 0
        evidence = BlackBoxEvidence(
            PublicObservation(execution.turns, "\n".join(turn.response for turn in execution.turns),
                              execution.public_objects, execution.attachments),
            FileObservation(before, after, difference.added, difference.modified, difference.deleted),
            ControlObservation(prepared.run_id, prepared.spec.case_id, prepared.repeat_index,
                               bool(health["ledger"]["healthy"]), positive_control_ok,
                               bool(health["healthy"])),
            prepared.baseline.tools.state if prepared.baseline.tools is not None else {},
            runtime.state if runtime is not None else {},
            execution.metrics,
        )
        environment.ledger.save_artifact(
            f"black_box_{prepared.spec.case_id}_repeat_{prepared.repeat_index}",
            {
                "scope": "PUBLIC/FILE/CONTROL black-box observations only",
                "public": {
                    "turns": [
                        {
                            "phase_id": turn.phase_id,
                            "response": turn.response,
                            "returncode": turn.returncode,
                            "completed": turn.completed,
                            "duration_seconds": turn.duration_seconds,
                            "session_id": turn.session_id,
                        }
                        for turn in evidence.public.turns
                    ],
                    "public_objects": list(evidence.public.public_objects),
                    "attachments": [str(path) for path in evidence.public.attachments],
                },
                "file": {
                    "added": list(evidence.files.added),
                    "modified": list(evidence.files.modified),
                    "deleted": list(evidence.files.deleted),
                    "before": [
                        {"path": entry.path, "sha256": entry.sha256, "is_directory": entry.is_directory}
                        for entry in evidence.files.before.entries
                    ],
                    "after": [
                        {"path": entry.path, "sha256": entry.sha256, "is_directory": entry.is_directory}
                        for entry in evidence.files.after.entries
                    ],
                },
                "control": {
                    "run_id": evidence.control.run_id,
                    "case_id": evidence.control.case_id,
                    "repeat_index": evidence.control.repeat_index,
                    "collector_ready": evidence.control.collector_ready,
                    "positive_control_ok": evidence.control.positive_control_ok,
                    "collection_complete": evidence.control.collection_complete,
                    "dropped_event_count": evidence.control.dropped_event_count,
                },
                "business_state_before": dict(evidence.business_state_before),
                "business_state_after": dict(evidence.business_state_after),
                "metrics": dict(evidence.metrics),
            },
        )
        return evidence
