# overlap_regression

## 1. detection
Capabilities that should be mutually exclusive appear to overlap, causing unexpected routing changes.

## 2. trace pattern
- Inspect `router_selected.tool_chain` for the chosen capability.
- Compare `predicate_eval` events for competing capabilities (same `normalized_text_hash`).
- If a partial response is returned, look for `partial_returned` after `router_selected`.

## 3. mitigation
- Confirm the currently loaded `capability_map_version` via `router_selected`.
- Validate that the deployed map matches the intended release.

## 4. rollback steps
- Mode A rollback: set `CAPABILITY_MAP_PATH` back to the default map.
