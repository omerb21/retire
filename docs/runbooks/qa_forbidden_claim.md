# qa_forbidden_claim

## 1. detection
A QA response is blocked due to forbidden claims or unsafe content policy.

## 2. trace pattern
- Look for `router_selected` with `mode=QA`.
- Confirm `schema_rendered` shows `output_schema_id` consistent with QA payloads.
- If a partial response is returned, look for `partial_returned`.

## 3. mitigation
- Adjust the prompt/request to remove the forbidden claim pattern.
- Confirm the capability used is the intended QA capability.

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` if the regression is due to a map change in routing to QA.
