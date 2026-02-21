from __future__ import annotations

import json
from typing import Any


def _canonicalize_value(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k in sorted(v.keys(), key=lambda x: str(x)):
            out[str(k)] = _canonicalize_value(v[k])
        return out
    if isinstance(v, (list, tuple)):
        return [_canonicalize_value(x) for x in v]
    try:
        return str(v)
    except Exception:
        return None


def canonicalize_tool_args(tool_name: str, args: dict, defaults: dict | None = None) -> dict:
    base = args if isinstance(args, dict) else {}
    merged: dict[str, Any] = {}
    if isinstance(defaults, dict):
        for k, v in defaults.items():
            merged[str(k)] = _canonicalize_value(v)
    for k, v in base.items():
        merged[str(k)] = _canonicalize_value(v)
    return _canonicalize_value(merged)


def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
