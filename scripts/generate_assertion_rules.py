#!/usr/bin/env python3
"""Generate assertion_rules from 预期结果.json for T-series cases."""

import json
from pathlib import Path
from typing import Any


def infer_assertion_rules(expected_result: Any) -> list[dict[str, Any]]:
    """Infer assertion rules from expected result JSON structure.

    Handles multiple patterns:
    - Top-level array → single assertion with metric 'result'
    - {topics: [...], actions: [...]} → generate two assertions
    - {summary: {...}, budget_unchanged: true, ...} → generate assertions per key
    - Single-key object → use that key as metric
    - Complex object → single assertion
    """
    rules = []

    # Pattern 0: Top-level array (e.g. T098-T101)
    if isinstance(expected_result, list):
        rules.append({
            "metric": "result",
            "operator": "eq",
            "expected": expected_result
        })
        return rules

    # Pattern 1: Has both 'topics' and 'actions' (e.g. T033, T034)
    if isinstance(expected_result, dict) and "topics" in expected_result and "actions" in expected_result:
        rules.append({
            "metric": "topics",
            "operator": "eq",
            "expected": expected_result["topics"]
        })
        rules.append({
            "metric": "actions",
            "operator": "eq",
            "expected": expected_result["actions"]
        })
        return rules

    # Pattern 2: Multiple top-level keys (e.g. T002: summary, budget_unchanged, project_unchanged)
    if isinstance(expected_result, dict) and len(expected_result) > 1:
        for key, value in expected_result.items():
            rules.append({
                "metric": key,
                "operator": "eq",
                "expected": value
            })
        return rules

    # Pattern 3: Single-key object (e.g. {reminder_source_keys: [...]})
    if isinstance(expected_result, dict) and len(expected_result) == 1:
        key = list(expected_result.keys())[0]
        rules.append({
            "metric": key,
            "operator": "eq",
            "expected": expected_result[key]
        })
        return rules

    # Pattern 4: Other structures - single assertion with 'result' metric
    if expected_result:
        rules.append({
            "metric": "result",
            "operator": "eq",
            "expected": expected_result
        })

    return rules


def main():
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "configs" / "black_box_t_series.json"
    assets_root = project_root / "assets" / "t_series"

    # Load config
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    updated_count = 0
    skipped_count = 0
    missing_count = 0

    for case in config["cases"]:
        case_id = case["case_id"]

        # Skip cases that already have assertion_rules
        if case.get("assertion_rules") and len(case["assertion_rules"]) > 0:
            skipped_count += 1
            continue

        # Check for expected result file
        expected_file = assets_root / case_id / "预期结果.json"
        if not expected_file.exists():
            missing_count += 1
            print(f"⚠️  {case_id}: 预期结果.json not found")
            continue

        # Load and generate rules
        try:
            with open(expected_file, encoding="utf-8") as f:
                expected_result = json.load(f)

            rules = infer_assertion_rules(expected_result)
            if rules:
                case["assertion_rules"] = rules
                updated_count += 1
                print(f"✅ {case_id}: generated {len(rules)} rule(s)")
            else:
                print(f"⚠️  {case_id}: could not infer rules from {expected_result}")
        except (OSError, json.JSONDecodeError) as e:
            print(f"❌ {case_id}: error reading file - {e}")
            missing_count += 1

    # Write updated config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n📊 Summary:")
    print(f"   Updated: {updated_count}")
    print(f"   Skipped (already has rules): {skipped_count}")
    print(f"   Missing/Error: {missing_count}")
    print(f"   Total cases: {len(config['cases'])}")
    print(f"\n✅ Config updated: {config_path}")


if __name__ == "__main__":
    main()
