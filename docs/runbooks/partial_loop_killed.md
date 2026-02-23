# partial_loop_killed

## 1. detection
The system repeatedly returns partial responses and fails to reach completion.

## 2. trace pattern
- Look for repeated `partial_returned` events within the same trace or across consecutive traces.
- Correlate upstream events:
  - `budget_guard_unenforceable`
  - `policy_gate_blocked`
  - missing `tool_finished` after `tool_started`

## 3. mitigation
- Identify which guard/event precedes `partial_returned`.
- Address the immediate blocker (policy, schema, tool failure) rather than retrying blindly.

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` to the stable map to restore previous routing.
