"""Verify JSON prompt paths map one-to-one to executable test case modules."""

from __future__ import annotations

import importlib

from test_cases.base import AgentTestCase
from test_cases.scenarios import cross_identity_replay as s01
from test_cases.scenarios import instance_id_boundaries as s02
from test_cases.scenarios import local_instance_state_tampering as s03
from test_cases.scenarios import natural_language_identity_override as s04
from test_cases.scenarios import tool_result_identity_injection as s05
from test_cases.security import SecurityIdentitySettings


EXPECTED_CASES = {
    "test_cases.test_cross_identity_b_instance": (
        "ATS-5.1b-D5-02-S01",
        "CROSS-ID-01",
    ),
    "test_cases.test_cross_identity_destroyed_instance": (
        "ATS-5.1b-D5-02-S01",
        "CROSS-ID-02",
    ),
    "test_cases.test_cross_identity_b_user_and_instance": (
        "ATS-5.1b-D5-02-S01",
        "CROSS-ID-03",
    ),
    "test_cases.test_null_instance_id": ("ATS-5.1b-D5-02-S02", "BOUNDARY-01"),
    "test_cases.test_unknown_instance_id": ("ATS-5.1b-D5-02-S02", "BOUNDARY-02"),
    "test_cases.test_oversized_instance_id": ("ATS-5.1b-D5-02-S02", "BOUNDARY-03"),
    "test_cases.test_json_instance_state_tampering": (
        "ATS-5.1b-D5-02-S03",
        "LOCAL-STATE-01",
    ),
    "test_cases.test_key_value_instance_state_tampering": (
        "ATS-5.1b-D5-02-S03",
        "LOCAL-STATE-02",
    ),
    "test_cases.test_direct_identity_claim": ("ATS-5.1b-D5-02-S04", "LANGUAGE-01"),
    "test_cases.test_admin_identity_override": ("ATS-5.1b-D5-02-S04", "LANGUAGE-02"),
    "test_cases.test_forged_system_identity": ("ATS-5.1b-D5-02-S04", "LANGUAGE-03"),
    "test_cases.test_text_tool_identity_injection": (
        "ATS-5.1b-D5-02-S05",
        "TOOL-INJECTION-01",
    ),
    "test_cases.test_structured_tool_identity_injection": (
        "ATS-5.1b-D5-02-S05",
        "TOOL-INJECTION-02",
    ),
}


class TestScenarioShapes:
    def test_sample_ids_and_repeat_counts(self) -> None:
        modules = (s01, s02, s03, s04, s05)

        assert [module.SAMPLE_ID for module in modules] == [
            "ATS-5.1b-D5-02-S01",
            "ATS-5.1b-D5-02-S02",
            "ATS-5.1b-D5-02-S03",
            "ATS-5.1b-D5-02-S04",
            "ATS-5.1b-D5-02-S05",
        ]
        assert all(module.REPEAT_COUNT == 3 for module in modules)

    def test_each_prompt_has_exactly_one_test_case_module(self) -> None:
        observed_case_ids: set[str] = set()

        for module_name, (sample_id, prompt_id) in EXPECTED_CASES.items():
            module = importlib.import_module(module_name)
            case_classes = [
                value
                for name, value in vars(module).items()
                if name.startswith("TestATS")
                and isinstance(value, type)
                and value.__module__ == module_name
            ]

            assert len(case_classes) == 1
            case_class = case_classes[0]
            assert issubclass(case_class, AgentTestCase)
            assert module.TEST_SAMPLE_ID == sample_id
            assert module.TEST_PROMPT_ID == prompt_id
            assert module.TEST_CASE_ID == f"{sample_id}-{prompt_id}"
            assert module.TEST_CASE_ID not in observed_case_ids
            assert module.TEST_CASE_ID in (case_class.__doc__ or "")
            observed_case_ids.add(module.TEST_CASE_ID)

        assert len(observed_case_ids) == 13

    def test_prompt_ids_and_turn_counts(self) -> None:
        settings = SecurityIdentitySettings(
            "token", "a-user", "a-instance", "b-user", "b-instance"
        )
        s01_variants = [
            s01._variant(name, settings, "destroyed-instance")
            for name in ("cross_01", "cross_02", "cross_03")
        ]

        assert [(item.prompt_id, len(item.turns)) for item in s01_variants] == [
            ("CROSS-ID-01", 2),
            ("CROSS-ID-02", 1),
            ("CROSS-ID-03", 2),
        ]
        assert [item.prompt_id for item in s02.VARIANTS] == [
            "BOUNDARY-01",
            "BOUNDARY-02",
            "BOUNDARY-03",
        ]
        assert [item.prompt_id for item in s03.VARIANTS] == [
            "LOCAL-STATE-01",
            "LOCAL-STATE-02",
        ]
        assert [item.prompt_id for item in s04.PROMPT_VARIANTS] == [
            "LANGUAGE-01",
            "LANGUAGE-02",
            "LANGUAGE-03",
        ]
        assert [item.prompt_id for item in s05.VARIANTS] == [
            "TOOL-INJECTION-01",
            "TOOL-INJECTION-02",
        ]

    def test_judge_criterion_counts(self) -> None:
        settings = SecurityIdentitySettings(
            "token", "a-user", "a-instance", "b-user", "b-instance"
        )
        s01_variants = [
            s01._variant(name, settings, "destroyed-instance")
            for name in ("cross_01", "cross_02", "cross_03")
        ]

        assert [
            (len(s01._pass_criteria(item)), len(s01._fail_criteria(item)))
            for item in s01_variants
        ] == [(6, 4), (7, 5), (6, 4)]
        for prompt_id in ("BOUNDARY-01", "BOUNDARY-02", "BOUNDARY-03"):
            assert (len(s02._pass_criteria(prompt_id)), len(s02._fail_criteria(prompt_id))) == (
                6,
                4,
            )
        for prompt_id in ("LOCAL-STATE-01", "LOCAL-STATE-02"):
            assert (len(s03._pass_criteria(prompt_id)), len(s03._fail_criteria(prompt_id))) == (
                6,
                4,
            )
        for prompt_id in ("LANGUAGE-01", "LANGUAGE-02", "LANGUAGE-03"):
            assert (len(s04._pass_criteria(prompt_id)), len(s04._fail_criteria(prompt_id))) == (
                6,
                4,
            )
        for prompt_id in ("TOOL-INJECTION-01", "TOOL-INJECTION-02"):
            assert (len(s05._pass_criteria(prompt_id)), len(s05._fail_criteria(prompt_id))) == (
                6,
                4,
            )
