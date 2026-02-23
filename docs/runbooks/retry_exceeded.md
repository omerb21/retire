# retry_exceeded

## 1. detection
Repeated attempts to complete a request fail, and the system keeps returning a partial response.

## 2. trace pattern
- Look for repeated sequences of:
  - `router_selected`
  - `tool_started` / `tool_finished` failures (where `tool_finished.success=false`)
  - `partial_returned`
- If `tool_finished.error_type` is present, group retries by the same error type.

## 3. mitigation
- Identify the failing tool via `tool_finished.tool_id`.
- Use the error type to route to the right owner (tool/service).

## 4. rollback steps
- Mode A rollback: point `CAPABILITY_MAP_PATH` to the stable map to avoid the failing chain.
