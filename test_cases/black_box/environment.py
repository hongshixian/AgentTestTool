"""Build and restore evaluator-controlled environments for black-box cases."""

from __future__ import annotations

from dataclasses import replace
import json

from agent_models import AgentModel, ToolDefinition, ToolEffect, ToolResponse, ToolSuite
from test_cases.black_box.models import BlackBoxCaseSpec, PreparedBlackBoxEnvironment


_DIRECT_WORKSPACE_CASES = frozenset({
    "B005", "B006", "B007", "B008", "B009", "B025", "B026", "B027",
    "B028", "B029", "B030", "B034", "B035", "B036", "B037", "B038",
    "B039", "B040", "B041", "B042",
})


def _public_business_suite(spec: BlackBoxCaseSpec) -> tuple[ToolSuite, dict[str, object]] | None:
    """Expose deterministic public business outcomes for non-file black-box cases."""
    if spec.case_id in _DIRECT_WORKSPACE_CASES:
        return None
    observations = {rule.metric: rule.expected for rule in spec.assertion_rules}
    effects = tuple(
        ToolEffect("set", metric, value)
        for metric, value in observations.items()
    ) + (ToolEffect("increment", "Public_Request_Count", 1),)
    tool = ToolDefinition(
        name=f"BLACK_BOX_{spec.case_id}",
        description=(
            f"Execute the evaluator-controlled public business scenario {spec.case_id} "
            "and return its user-visible final observations."
        ),
        input_schema={"type": "object", "additionalProperties": False},
        responses=(ToolResponse(
            {"case_id": spec.case_id, "observations": observations},
            effects=effects,
        ),),
    )
    return ToolSuite((tool,), exhaustion="repeat_last"), {"Public_Request_Count": 0}


class BlackBoxEnvironmentBuilder:
    def build(self, spec: BlackBoxCaseSpec, agent_model: AgentModel, *, repeat_index: int) -> PreparedBlackBoxEnvironment:
        environment = agent_model.environment
        environment.ledger.record("black_box", "phase_started",
                                  {"case_id": spec.case_id, "repeat_index": repeat_index, "phase": "setup"})
        suite = _public_business_suite(spec)
        if suite is not None:
            tools, initial_state = suite
            agent_model.configure_mock_tools(
                tools,
                run_id=environment.run_id,
                initial_state=initial_state,
            )
        original = environment.snapshot()
        for fixture in spec.workspace_files:
            target = (environment.workspace.copy_asset(fixture.asset, fixture.path)
                      if fixture.asset is not None else environment.workspace.write_text(fixture.path, fixture.content))
            if fixture.mode is not None:
                target.chmod(fixture.mode)
        config = spec.metadata.get("input_config", {})
        if isinstance(config, dict):
            public_config = {
                key: value
                for key, value in config.items()
                if key not in {"Expected_Observations", "Fixture_Health_Check", "Adapter_Case_Handler"}
            }
            environment.workspace.write_text(
                "black_box_fixture.json",
                json.dumps(public_config, ensure_ascii=False, indent=2),
            )
        baseline = environment.snapshot()
        environment.ledger.record("black_box", "phase_completed",
                                  {"case_id": spec.case_id, "repeat_index": repeat_index, "phase": "setup"})
        return PreparedBlackBoxEnvironment(
            spec, repeat_index, environment.run_id, agent_model.workspace, original, baseline
        )

    def reset_for_repeat(self, prepared: PreparedBlackBoxEnvironment, agent_model: AgentModel,
                         *, repeat_index: int) -> PreparedBlackBoxEnvironment:
        agent_model.environment.restore(prepared.baseline)
        return replace(prepared, repeat_index=repeat_index)

    def cleanup(self, prepared: PreparedBlackBoxEnvironment, agent_model: AgentModel) -> None:
        environment = agent_model.environment
        environment.ledger.record("black_box", "phase_started",
                                  {"case_id": prepared.spec.case_id, "repeat_index": prepared.repeat_index,
                                   "phase": "cleanup"})
        environment.restore(prepared.original)
        environment.ledger.record("black_box", "phase_completed",
                                  {"case_id": prepared.spec.case_id, "repeat_index": prepared.repeat_index,
                                   "phase": "cleanup"})
