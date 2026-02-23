# schema_render_failure

## 1. detection
The system returns a schema-related failure, or downstream validation rejects the assistant output.

## 2. trace pattern
- Look for `schema_rendered`:
  - Confirm `output_schema_id`
  - Inspect `result_keys` (keys only; values are not logged)
- If the system falls back to partial, look for `partial_returned`.

## 3. mitigation
- Confirm the expected output schema is deployed.
- Reproduce with the same capability (from `router_selected.capability_id`).

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` to the stable map version.
