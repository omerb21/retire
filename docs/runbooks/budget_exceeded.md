# budget_exceeded

## 1. detection
The system returns a partial response indicating budgeting/timeout limitations.

## 2. trace pattern
- Look for `partial_returned` with `status` indicating a budgeting/timeout outcome.
- If budgeting is unenforceable, look for `budget_guard_unenforceable` preceding `partial_returned`.
- Correlate whether any `tool_started` occurred before the partial.

## 3. mitigation
- If `budget_guard_unenforceable` is present, treat it as a configuration/runtime-context limitation.
- Reduce request complexity or adjust the routing/map to avoid long tool chains.

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` to the stable map.
