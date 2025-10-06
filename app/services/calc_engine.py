from typing import Any, Dict, List, Optional

def calculate_client(client_id: int, scenario_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Stage-8 skeleton: נקודת איסוף לחישובים. בהמשך יתווספו חיבורי מס/מדד/קיבוע.
    שמור על חתימה זו לצורך תאימות קדימה.
    """
    return {
        "client_id": client_id,
        "scenarios": scenario_ids or [],
        "result": "ok",
        "engine_version": "stage8-skeleton-1",
    }
