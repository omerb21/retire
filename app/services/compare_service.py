from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Tuple
from app.services.cashflow_service import generate_cashflow
from app.utils.calculation_log import log_calc
import os


def _yearly_totals(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    עוזר: הפקת (year -> totals) עבור רשימת שורות תזרים
    שדות לצבירה: inflow, outflow, additional_income_net, capital_return_net, net
    """
    acc: Dict[str, Dict[str, float]] = defaultdict(lambda: {
        "inflow": 0.0, 
        "outflow": 0.0, 
        "additional_income_net": 0.0, 
        "capital_return_net": 0.0, 
        "net": 0.0
    })
    
    for r in rows:
        # תאריך יכול להיות str "YYYY-MM-DD" או date — לאחד ל-YYYY
        d = r["date"]
        if hasattr(d, "strftime"):
            y = d.strftime("%Y")
        else:
            y = str(d)[:4]
            
        acc[y]["inflow"] += float(r.get("inflow", 0) or 0)
        acc[y]["outflow"] += float(r.get("outflow", 0) or 0)
        acc[y]["additional_income_net"] += float(r.get("additional_income_net", 0) or 0)
        acc[y]["capital_return_net"] += float(r.get("capital_return_net", 0) or 0)
        acc[y]["net"] += float(r.get("net", 0) or 0)
    
    return {year: {k: round(v, 2) for k, v in totals.items()} for year, totals in acc.items()}


def compare_scenarios(
    db_session,
    client_id: int,
    scenario_ids: List[int],
    from_yyyymm: str,
    to_yyyymm: str,
    frequency: str = "monthly",
) -> Dict[str, Any]:
    """
    משווה מספר תרחישים עבור לקוח נתון ומחזיר תזרים חודשי וטוטלים שנתיים
    """
    # Log calculation start
    payload = {
        "client_id": client_id,
        "scenario_ids": scenario_ids,
        "from_yyyymm": from_yyyymm,
        "to_yyyymm": to_yyyymm,
        "frequency": frequency
    }
    
    debug_info = None
    if os.getenv("DEBUG_CALC", "0") == "1":
        debug_info = {
            "validation_checks": {
                "frequency_supported": frequency == "monthly",
                "scenario_count": len(scenario_ids)
            }
        }
    
    # ולידציה בסיסית (ספרינט 7 כבר בודק בפונקציות קיימות, כאן מחזקים)
    if frequency != "monthly":
        log_calc("compare_scenarios_error", payload, None, {"error": "Invalid frequency"})
        raise ValueError("Only 'monthly' is supported")

    # הפקת תזרים עבור כל תרחיש
    result: Dict[str, Any] = {
        "scenarios": {}, 
        "meta": {
            "client_id": client_id, 
            "from": from_yyyymm, 
            "to": to_yyyymm, 
            "frequency": frequency
        }
    }
    
    for sid in scenario_ids:
        # משתמש בפונקציה הקיימת מספרינט 7
        rows = generate_cashflow(db_session, client_id, sid, from_yyyymm, to_yyyymm)
        
        # נוודא שהשדה date יחזור כ-YYYY-MM-DD (מחרוזת) — אחידות
        norm_rows = []
        for r in rows:
            d = r["date"]
            if hasattr(d, "strftime"):
                d = d.strftime("%Y-%m-%d")
            else:
                d = str(d)
            nr = dict(r)
            nr["date"] = d
            norm_rows.append(nr)
            
        result["scenarios"][str(sid)] = {
            "monthly": norm_rows,
            "yearly": _yearly_totals(norm_rows),
        }
    
    # Logical validation checks
    _validate_scenario_results(result)
    
    # Log successful completion
    log_calc("compare_scenarios", payload, result, debug_info)
    return result


def _validate_scenario_results(result: Dict[str, Any]):
    """
    Validate scenario comparison results for logical consistency
    Checks for negative taxes, extreme values, etc.
    """
    warnings = []
    
    for scenario_id, scenario_data in result.get("scenarios", {}).items():
        yearly_data = scenario_data.get("yearly", {})
        
        for year, totals in yearly_data.items():
            # Check for extremely negative net values (potential calculation error)
            net = totals.get("net", 0)
            if net < -1000000:  # Less than -1M NIS per year
                warnings.append(f"Scenario {scenario_id}, Year {year}: Extremely negative net cashflow ({net:,.0f})")
            
            # Check for unrealistic positive values
            inflow = totals.get("inflow", 0)
            if inflow > 50000000:  # More than 50M NIS per year
                warnings.append(f"Scenario {scenario_id}, Year {year}: Unrealistic inflow amount ({inflow:,.0f})")
            
            # Check for negative additional income (should be positive or zero)
            add_income = totals.get("additional_income_net", 0)
            if add_income < -100000:  # Less than -100K (some negative is OK for taxes)
                warnings.append(f"Scenario {scenario_id}, Year {year}: Suspicious additional income ({add_income:,.0f})")
    
    # Log warnings if any
    if warnings:
        log_calc("validation_warnings", {"scenario_count": len(result.get("scenarios", {}))}, warnings)
