"""Verify context scenarios require complete observations before interaction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_models.capabilities import AgentCapabilities
from test_cases.scenarios import cross_identity_replay as s01
from test_cases.scenarios import instance_id_boundaries as s02
from test_cases.scenarios import local_instance_state_tampering as s03
from test_cases.security import SecurityIdentitySettings


class _BoundaryCheckReached(RuntimeError):
    pass


class TestContextRequirements:
    @pytest.mark.parametrize(
        ("scenario", "variant"),
        [
            ("cross", "cross_01"),
            ("cross", "cross_02"),
            ("cross", "cross_03"),
            *(("boundary", variant) for variant in s02.VARIANTS),
            *(("local", variant) for variant in s03.VARIANTS),
        ],
    )
    def test_complete_observation_is_checked_before_identity_or_interaction(
        self,
        monkeypatch: pytest.MonkeyPatch,
        scenario: str,
        variant: object,
    ) -> None:
        agent = SimpleNamespace(
            capabilities=AgentCapabilities(
                multi_turn=True,
                dedicated_test_account=True,
                external_observation=True,
                public_identity_context=True,
                local_state_control=True,
            )
        )
        if scenario == "cross":
            runner = s01.CrossIdentityScenarioRunner()
            execute = runner.run_cross_identity_context_cannot_gain_access
        elif scenario == "boundary":
            runner = s02.InstanceIdBoundaryScenarioRunner()
            execute = runner.run_invalid_instance_id_is_rejected_without_side_effects
        else:
            runner = s03.LocalInstanceStateScenarioRunner()
            execute = runner.run_local_instance_tampering_is_detected_and_restored

        def require_boundary_observation(model: object, request: object) -> None:
            assert model is agent
            raise _BoundaryCheckReached

        def reject_early_identity_read(request: object, model: object) -> None:
            pytest.fail("身份配置读取前必须先判断完整安全观察能力")

        monkeypatch.setattr(
            runner,
            "require_security_boundary_observation",
            require_boundary_observation,
            raising=False,
        )
        monkeypatch.setattr(runner, "require_security_identities", reject_early_identity_read)

        with pytest.raises(_BoundaryCheckReached):
            execute(agent, None, object(), variant, 1)

    def test_cross_identity_prompts_do_not_disclose_the_private_marker(self) -> None:
        identities = SecurityIdentitySettings(
            "test-user-a", "test-instance-a", "test-user-b", "test-instance-b"
        )

        for name in ("cross_01", "cross_02", "cross_03"):
            variant = s01._variant(name, identities, "test-destroyed-instance")
            assert all(s01.PRIVATE_MARKER not in prompt for prompt in variant.turns)

    def test_boundary_values_preserve_null_unknown_and_exact_ascii_length(self) -> None:
        assert s02.VARIANTS[0].instance_id is None
        assert s02.VARIANTS[1].instance_id == "UNKNOWN-404"
        assert s02.VARIANTS[2].instance_id == "A" * 8192
