#!/usr/bin/env python3
"""Update T-series test wrappers to use judge_model fixture."""

from pathlib import Path


def main():
    test_dir = Path("test_cases/black_box")
    test_files = sorted(test_dir.glob("test_t*.py"))

    updated_count = 0

    for test_file in test_files:
        content = test_file.read_text(encoding="utf-8")

        # Skip if already has judge_model
        if "judge_model" in content:
            continue

        # Add judge_model parameter
        if "request: pytest.FixtureRequest," in content:
            content = content.replace(
                "request: pytest.FixtureRequest,",
                "request: pytest.FixtureRequest,\n        judge_model = None,"
            )

        # Pass judge_model to runner
        if "request=request," in content and "judge_model=judge_model," not in content:
            content = content.replace(
                "request=request,",
                "request=request,\n            judge_model=judge_model,"
            )

        test_file.write_text(content, encoding="utf-8")
        updated_count += 1
        print(f"Updated {test_file.name}")

    print(f"\nTotal updated: {updated_count} files")


if __name__ == "__main__":
    main()
