def compute_rights_fixation(client_id: int, payload: dict | None = None) -> dict:
    """
    קלט: client_id, payload אופציונלי (לכיוון עתידי).
    מחזיר: dict עם מפתחות: client_id, inputs, outputs, engine_version.
    
    אם קיים מודול חיצוני של קיבוע – קרא אליו; אם לא – החזר חישוב דמה עקבי.
    """
    # For now, return consistent dummy calculation
    # In the future, this would call external fixation module
    
    inputs = {
        "client_id": client_id,
        "scenario_id": payload.get("scenario_id") if payload else None,
        "params": payload.get("params", {}) if payload else {},
        "timestamp": "2025-08-10T09:42:52+03:00"
    }
    
    outputs = {
        "exempt_capital_remaining": 0.0,
        "used_commutation": 0.0,
        "annex_161d_ready": False
    }
    
    return {
        "client_id": client_id,
        "inputs": inputs,
        "outputs": outputs,
        "engine_version": "fixation-sprint2-1"
    }
