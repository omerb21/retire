# Runbooks

These runbooks are for operational mitigation and rollback.

All runbooks follow the same structure:

1. detection
2. trace pattern
3. mitigation
4. rollback steps

Rollback priority:

- Mode A (map-only) rollback first: set `CAPABILITY_MAP_PATH` back to the default map path.
