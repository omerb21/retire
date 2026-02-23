# tool_timeout

## 1. detection
A tool call appears to hang or takes too long, or the user reports that execution never completes.

## 2. trace pattern
- Look for `tool_started` without a matching `tool_finished` for the same `tool_id` within the same trace.
- If a partial response is returned due to a guard, look for `partial_returned`.

## 3. mitigation
- Identify the tool via `tool_started.tool_id`.
- Correlate with infrastructure logs for that tool/service.

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` to the default map to avoid routing to the problematic tool chain.
