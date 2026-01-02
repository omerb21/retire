import json

from app.services.retirement.constants import MINIMUM_PENSION


def handle_get_system_numeric_constants(*, args: dict) -> str:
    return json.dumps(
        {
            "success": True,
            "tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
            "result": {
                "MINIMUM_PENSION": {
                    "value": float(MINIMUM_PENSION),
                    "unit": "ILS",
                }
            },
        },
        ensure_ascii=False,
    )
