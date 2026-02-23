# routing_drift

## 1. detection
Routing outcomes differ between environments, or a request that used to route to a specific capability now routes differently.

## 2. trace pattern
- Look for `router_selected` and compare:
  - `capability_id`
  - `capability_map_version`
  - `router_normalization_version`
  - `normalized_text_hash`
- If drift is suspected due to matching differences, compare `predicate_eval` sequences (by `rule_id` and `outcome`) for the same `normalized_text_hash`.

## 3. mitigation
- Verify the runtime map path by checking the environment variable `CAPABILITY_MAP_PATH`.
- Confirm that the expected capability map file is deployed.

## 4. rollback steps
- Mode A rollback: unset `CAPABILITY_MAP_PATH` or point it back to the default `capability_map.yaml`.
