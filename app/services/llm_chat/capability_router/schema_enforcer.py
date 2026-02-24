from __future__ import annotations

import re
from typing import Any

from app.services.llm_chat.capability_router.ssot_loader import load_output_schemas

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\-\.]+)\s*\}\}")


def _contains_disallowed_placeholders(value: str, allowlist: set[str]) -> bool:
    if not allowlist:
        return False
    if not isinstance(value, str) or "{{" not in value or "}}" not in value:
        return False
    for m in _PLACEHOLDER_RE.finditer(value):
        key = m.group(1)
        if key not in allowlist:
            return True
    return False


def _validate_schema_node(
    schema: dict[str, Any], value: Any, *, placeholder_allowlist: set[str]
) -> bool:
    if not isinstance(schema, dict):
        return False

    t = schema.get("type")

    if t == "object":
        if not isinstance(value, dict):
            return False

        props = (
            schema.get("properties")
            if isinstance(schema.get("properties"), dict)
            else {}
        )
        required = (
            schema.get("required") if isinstance(schema.get("required"), list) else []
        )
        additional = schema.get("additionalProperties")

        for rk in required:
            if isinstance(rk, str) and rk not in value:
                return False

        if additional is False:
            for k in value.keys():
                if k not in props:
                    return False

        for k, subschema in props.items():
            if k in value:
                if not _validate_schema_node(
                    subschema, value[k], placeholder_allowlist=placeholder_allowlist
                ):
                    return False

        return True

    if t == "array":
        if not isinstance(value, list):
            return False
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            return False
        items_schema = (
            schema.get("items") if isinstance(schema.get("items"), dict) else None
        )
        if items_schema is not None:
            for item in value:
                if not _validate_schema_node(
                    items_schema, item, placeholder_allowlist=placeholder_allowlist
                ):
                    return False
        return True

    if t == "string":
        if not isinstance(value, str):
            return False
        enum = schema.get("enum")
        if isinstance(enum, list) and value not in enum:
            return False
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and len(value) < min_len:
            return False
        if _contains_disallowed_placeholders(value, placeholder_allowlist):
            return False
        return True

    if t == "boolean":
        return value in {True, False}

    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)

    return False


def enforce_output_schema(
    *,
    output_schema_id: str,
    payload: dict[str, Any],
    detected_capability_id: str,
    placeholder_allowlist: set[str] | None = None,
) -> dict[str, Any]:
    """Enforce schema strictly.

    On failure: return deterministic partial_result_v1 (no free text fallback).
    """

    allowlist = placeholder_allowlist or set()

    try:
        schemas_doc = load_output_schemas()
        schemas = (
            schemas_doc.get("schemas")
            if isinstance(schemas_doc.get("schemas"), dict)
            else {}
        )
        schema = (
            schemas.get(output_schema_id) if isinstance(output_schema_id, str) else None
        )
        if not isinstance(schema, dict):
            raise ValueError("unknown_schema")

        ok = _validate_schema_node(schema, payload, placeholder_allowlist=allowlist)
        if ok:
            return payload
        raise ValueError("schema_validation_failed")
    except Exception:
        # Deterministic partial schema only.
        return {
            "mode": "QA",
            "status": "schema_error",
            "detected_capability_id": str(detected_capability_id or "unknown"),
            "what_ran": [],
            "missing_fields": [],
            "next_step": "contact_support",
        }
