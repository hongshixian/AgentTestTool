"""Build and restore evaluator-controlled environments for black-box cases."""

from __future__ import annotations

from dataclasses import replace
import json

from agent_models import AgentModel, ToolDefinition, ToolEffect, ToolResponse, ToolSuite
from test_cases.black_box.config import EnvironmentConfig
from test_cases.black_box.models import BlackBoxCaseSpec, PreparedBlackBoxEnvironment
from test_cases.black_box.profiles import profile_for


_BLACK_BOX_MAX_TURNS = 50


def _public_business_suite(spec: BlackBoxCaseSpec) -> tuple[ToolSuite, dict[str, object]] | None:
    """Expose a deterministic submission tool for non-file black-box cases.

    Design (post-fix):
    - The tool NO LONGER pre-loads expected answers into its response body.
      Previously the response contained ``{"observations": <expected>}`` which
      let the agent echo the answer without doing any real work.
    - For cases whose only assertion metric is ``expected_result`` (free-text),
      no tool is exposed at all; the agent completes the task using its native
      product tools and Judge evaluates the response text.
    - For all other cases the tool accepts ``{"result": <agent's answer>}`` and
      writes each field to runtime state via ``argument_path``.  The handler
      then reads ``state["agent_result_<metric>"]`` and compares it to the
      expected value from assertion_rules.
    """
    profile = profile_for(spec)
    if not profile.has_submission_tool:
        return None

    # Build a submission schema and argument_path effects for each metric.
    result_properties: dict = {}
    effects: list[ToolEffect] = []
    for metric in profile.submission_metrics:
        # No type constraint in the schema: the agent submits what it observes,
        # and the handler compares to expected.  Type enforcement is in the
        # assertion layer, not the submission gate.
        result_properties[metric] = {}
        # Copy agent-submitted value into state under a distinct key so
        # _state_handler can retrieve it without confusing expected vs actual.
        effects.append(ToolEffect(
            "set", f"agent_result_{metric}",
            argument_path=("result", metric),
        ))
    effects.append(ToolEffect("increment", "Public_Request_Count", 1))

    # Build a human-readable description of the expected format for each metric.
    metric_format_hints = []
    rule_by_metric = {r.metric: r for r in spec.assertion_rules if r.metric in profile.submission_metrics}
    for metric in profile.submission_metrics:
        rule = rule_by_metric.get(metric)
        expected = rule.expected if rule else None
        if isinstance(expected, str):
            hint = f"{metric}（字符串，例如：\"{expected}\"）"
        elif isinstance(expected, bool):
            hint = f"{metric}（布尔值，例如：{str(expected).lower()}）"
        elif isinstance(expected, list):
            sample = json.dumps(expected[:2], ensure_ascii=False) if expected else "[]"
            hint = f"{metric}（数组，例如：{sample}）"
        elif isinstance(expected, dict):
            hint = f"{metric}（对象）"
        elif expected is not None:
            hint = f"{metric}（值：{json.dumps(expected, ensure_ascii=False)}）"
        else:
            hint = f"{metric}"
        metric_format_hints.append(hint)
    format_hint_str = "；".join(metric_format_hints)

    tool = ToolDefinition(
        name=f"BLACK_BOX_{spec.case_id}",
        description=(
            f"Submit the outcome of business scenario {spec.case_id}. "
            f"Call this tool with the result object after completing the task. "
            f"Expected fields and their value format: {format_hint_str}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "result": {
                    "type": "object",
                    "description": "Your actual observed outcome keyed by metric name.",
                    "properties": result_properties,
                    "required": list(result_properties),
                    "additionalProperties": False,
                },
            },
            "required": ["result"],
            "additionalProperties": False,
        },
        responses=(ToolResponse(
            {"case_id": spec.case_id, "status": "recorded"},
            effects=tuple(effects),
        ),),
    )
    return ToolSuite((tool,), exhaustion="repeat_last"), {"Public_Request_Count": 0}


class BlackBoxEnvironmentBuilder:
    def build(self, spec: BlackBoxCaseSpec, agent_model: AgentModel, *, repeat_index: int) -> PreparedBlackBoxEnvironment:
        """Build an environment from a spec. Derive config on the fly for now.

        TODO: Once all callers are updated to pass EnvironmentConfig directly,
        change signature to accept config instead of spec.
        """
        config = EnvironmentConfig.from_spec(spec, agent_model.workspace)
        return self._build_from_config(spec, config, agent_model, repeat_index=repeat_index)

    def _build_from_config(
        self, spec: BlackBoxCaseSpec, config: EnvironmentConfig, agent_model: AgentModel, *, repeat_index: int
    ) -> PreparedBlackBoxEnvironment:
        environment = agent_model.environment
        environment.ledger.record("black_box", "phase_started",
                                  {"case_id": config.case_id, "repeat_index": repeat_index, "phase": "setup"})
        if config.tool_suite is not None:
            agent_model.configure_mock_tools(
                config.tool_suite,
                run_id=environment.run_id,
                initial_state=config.suite_metadata,
                # Black-box tasks do real multi-step file work; the grey-box
                # default of 4 agent turns ends them before they finish.
                max_turns=_BLACK_BOX_MAX_TURNS,
                suite_type="black_box",
            )
        original = environment.snapshot()
        for fixture in config.workspace_files:
            # A path that ends with '/' and has no asset is a directory stub:
            # create the directory and apply the declared mode, if any.
            is_dir_stub = fixture.asset is None and str(fixture.path).endswith("/")
            if is_dir_stub:
                target = environment.workspace.root / fixture.path.rstrip("/")
                target.mkdir(parents=True, exist_ok=True)
            else:
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
