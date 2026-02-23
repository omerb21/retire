# policy_gate_blocked

## 1. detection
A tool call is blocked by policy, returning a policy-related partial response.

## 2. trace pattern
- Look for `policy_gate_blocked`.
- Check `router_selected.capability_id` and the selected `tool_chain`.
- If a partial response is returned, verify `partial_returned` exists after the block.

## 3. mitigation
- Confirm the capability/tool is expected to require policy approval.
- Verify policy configuration and any allowlists/permissions.

## 4. rollback steps
- Mode A rollback: revert `CAPABILITY_MAP_PATH` to the previous stable map if the policy gate behavior changed with the map.
