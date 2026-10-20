#!/bin/bash
# Check progress of running tests

cd "$(dirname "$0")/.."

echo "=== Test Execution Progress ==="
echo ""

# Check if process is running
if ps aux | grep -v grep | grep "agent-test.*openclaw" > /dev/null; then
    echo "✓ Test process is running"
else
    echo "✗ Test process not found"
fi

echo ""

# Count completed tests
latest_run=$(ls -td artifacts/*/ 2>/dev/null | head -1)
if [ -n "$latest_run" ]; then
    echo "Latest run directory: $latest_run"

    completed_count=$(find "$latest_run" -name "pytest_outcome.json" -type f 2>/dev/null | wc -l)
    passed_count=$(find "$latest_run" -name "pytest_outcome.json" -type f -exec grep -l '"assessment_status":"通过"' {} \; 2>/dev/null | wc -l)
    failed_count=$(find "$latest_run" -name "pytest_outcome.json" -type f -exec grep -l '"assessment_status":"不通过"' {} \; 2>/dev/null | wc -l)

    echo "  Completed: $completed_count tests"
    echo "  Passed: $passed_count"
    echo "  Failed: $failed_count"

    # Check for PDF report
    if [ -f "${latest_run}report.pdf" ]; then
        size=$(ls -lh "${latest_run}report.pdf" | awk '{print $5}')
        echo "  ✓ PDF Report: ${size}"
    else
        echo "  ⏳ PDF Report: Not yet generated"
    fi
fi

echo ""
echo "=== Recent Log Tail ==="
if [ -f "logs/openclaw_full_run.log" ]; then
    tail -10 logs/openclaw_full_run.log 2>&1 | head -10
else
    echo "Log file not found"
fi
