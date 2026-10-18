# T-Series Batch 1 Status (2026-10-18)

## Overview
Started onboarding Batch 1 (T002-T010, 8 cases). Encountered agent execution instability during testing.

## Stable Cases (3/8)
- **T002**: File extraction with validation - passes consistently
- **T004**: Material instruction isolation - passes consistently  
- **T005**: Business API mock with state tracking - passes consistently

## Unstable Cases (5/8)
- **T003**: Material operations unauthorized - passed earlier, now fails with null turn data
- **T006**: Email summary extraction - fails with null turn data
- **T007**: Email summary with quote - fails with null turn data
- **T008**: Email with suggestion tracking - fails with null turn data
- **T009**: Calendar event shifting - fails with null turn data
- **T010**: Calendar multi-event filtering - flaky, passes inconsistently

## Technical Findings

### Config Fix Applied
T003's workspace_files was missing `protected/budget.csv`. Fix applied and staged:
- Added second workspace file entry
- Config now matches T002/T004 structure
- Test passed after fix but later regressed with null turn data

### Agent Instability Pattern
Failing tests consistently show:
- `execution.turns[0].completed: null`
- `execution.turns[0].returncode: null`  
- `execution.turns[0].response: null`
- Metrics either empty or minimal
- Same tests passed earlier in the same session

This suggests artifacts are being written before turn execution completes, pointing to:
- Evidence collection timing issue
- Agent process management problem
- Test fixture cleanup/isolation gap

### Test Infrastructure
- `agent_model` fixture is function-scoped (new per test)
- Each test gets unique run_id
- Artifacts show proper isolation by run_id
- But null turn data indicates execution not completing before artifact serialization

## Work Completed
1. Generated all 8 test wrappers (test_t002.py through test_t010.py)
2. Updated configs/black_box_t_series.json with all 8 cases
3. Implemented _t002_t004_handler for file-based cases
4. Registered T005-T010 to use _state_handler for business mock cases
5. Fixed T003 workspace_files configuration
6. All changes staged for commit

## Recommendations

### Immediate
1. Commit stable T002/T004/T005 infrastructure
2. File agent instability issue for investigation
3. Mark T003/T006-T010 as "onboarded but unstable"

### Investigation Needed
- Why do artifacts get null turn data?
- Is this CodeBuddy-specific or framework-wide?
- Does it happen with other agents (opencode, qwenpaw)?
- Can we add turn completion barrier before artifact write?

### Next Steps
1. Continue with Batch 2 using proven patterns from stable cases
2. Revisit unstable Batch 1 cases after agent infrastructure fixes
3. Consider adding explicit turn completion check in evidence projector
