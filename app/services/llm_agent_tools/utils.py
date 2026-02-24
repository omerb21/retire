from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return _to_jsonable(dumped)
    dict_dump = getattr(value, "dict", None)
    if callable(dict_dump):
        dumped = dict_dump()
        return _to_jsonable(dumped)

    raw = getattr(value, "__dict__", None)
    if isinstance(raw, dict):
        return _to_jsonable(raw)

    return str(value)
