#!/bin/bash
# Monitor progress of all 4 agent test runs

cd "$(dirname "$0")/.."

echo "════════════════════════════════════════════════════════"
echo "  Agent Test Suite Progress Monitor"
echo "  Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"
echo ""

# Function to check one agent
check_agent() {
    local agent=$1
    local process_pattern="agent-test.*--agent $agent"

    echo "[$agent]"

    # Check if running
    if ps aux | grep -v grep | grep "$process_pattern" > /dev/null 2>&1; then
        echo "  Status: ✓ Running"
    else
        echo "  Status: ✗ Not running / Completed"
    fi

    # Find latest run directory for this agent
    local run_dir=$(find artifacts -type d -name "*" -exec grep -l "\"agent\":\"$agent\"" {}/manifest.json 2>/dev/null \; | head -1 | xargs dirname 2>/dev/null)

    if [ -n "$run_dir" ]; then
        local completed=$(find "$run_dir" -name "pytest_outcome.json" -type f 2>/dev/null | wc -l)
        local passed=$(find "$run_dir" -name "pytest_outcome.json" -type f -exec grep -l '"assessment_status":"通过"' {} \; 2>/dev/null | wc -l)
        local failed=$(find "$run_dir" -name "pytest_outcome.json" -type f -exec grep -l '"assessment_status":"不通过"' {} \; 2>/dev/null | wc -l)

        local percent=0
        if [ $completed -gt 0 ]; then
            percent=$((completed * 100 / 292))
        fi

        echo "  Progress: $completed/292 tests ($percent%)"
        echo "  Passed: $passed | Failed: $failed"

        # Check for reports
        if [ -f "$run_dir/report.json" ]; then
            echo "  ✓ JSON Report generated"
        fi

        if [ -f "$run_dir/report.pdf" ]; then
            local size=$(ls -lh "$run_dir/report.pdf" | awk '{print $5}')
            echo "  ✓ PDF Report: $size"
        else
            echo "  ⏳ PDF Report: Pending"
        fi

        echo "  Run directory: $run_dir"
    else
        echo "  No run directory found yet"
    fi

    echo ""
}

# Check all 4 agents
check_agent "openclaw"
check_agent "codebuddy"
check_agent "qwenpaw"
check_agent "codex"

echo "════════════════════════════════════════════════════════"
echo "Summary:"
echo "════════════════════════════════════════════════════════"

# Count total PDFs generated
pdf_count=$(find artifacts -name "report.pdf" -type f -mmin -120 2>/dev/null | wc -l)
echo "PDF Reports generated: $pdf_count/4"

# Show running processes
running_count=$(ps aux | grep -v grep | grep "agent-test" | wc -l)
echo "Active test processes: $running_count"

echo ""
echo "To check logs:"
echo "  tail -f logs/openclaw_full_run.log"
echo "  tail -f logs/codebuddy_full_run.log"
echo "  tail -f logs/qwenpaw_full_run.log"
echo "  tail -f logs/codex_full_run.log"
