from datetime import datetime, date
from collections import defaultdict
from typing import Dict, List, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
import collections.abc as cabc
from app.services.cashflow_service import generate_cashflow
from app.services.case_service import detect_case
from app.utils.calculation_log import log_calc
from app.utils.date_serializer import normalize_cashflow_row, extract_year_from_date
import os


def _to_decimal(v: Any) -> Decimal:
    """
    Convert value to Decimal, handling None and empty values
    """
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _round2(v: Decimal) -> float:
    """
    Round to 2 decimal places and convert to float
    """
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _compute_yearly_from_months(monthly_rows):
    """
    Compute yearly totals from monthly data with precise decimal calculations
    monthly_rows: list of dicts with keys inflow, outflow, additional_income_net, capital_return_net, net (optionally)
    """
    inflow = Decimal("0")
    outflow = Decimal("0")
    add_net = Decimal("0")
    cap_net = Decimal("0")
    
    for r in monthly_rows:
        inflow += _to_decimal(r.get("inflow"))
        outflow += _to_decimal(r.get("outflow"))
        add_net += _to_decimal(r.get("additional_income_net"))
        cap_net += _to_decimal(r.get("capital_return_net"))
    
    net = inflow - outflow + add_net + cap_net
    
    return {
        "inflow": _round2(inflow),
        "outflow": _round2(outflow),
        "additional_income_net": _round2(add_net),
        "capital_return_net": _round2(cap_net),
        "net": _round2(net),
    }


def compare_scenarios(
    db_session,
    client_id: int,
    scenario_ids: List[int],
    from_yyyymm: str,
    to_yyyymm: str,
    frequency: str = "monthly",
    case_id: int = None,
) -> Dict[str, Any]:
    """
    משווה מספר תרחישים עבור לקוח נתון ומחזיר תזרים חודשי וטוטלים שנתיים
    חזרה בפורמט חדש: scenarios[] כרשימה
    """
    # Auto-detect case if not provided
    if case_id is None:
        case_detection_result = detect_case(db_session, client_id)
        case_id = case_detection_result.case_id
        case_name = case_detection_result.case_name
        case_reasons = case_detection_result.reasons
    else:
        # Just get case name for logging
        try:
            case_detection_result = detect_case(db_session, client_id)
            case_name = case_detection_result.case_name
            case_reasons = case_detection_result.reasons
        except Exception:
            # If detection fails but case_id was provided, use defaults
            case_name = f"CASE_{case_id}"
            case_reasons = ["manually_provided"]
    
    # Log calculation start
    payload = {
        "client_id": client_id,
        "scenario_ids": scenario_ids,
        "from_yyyymm": from_yyyymm,
        "to_yyyymm": to_yyyymm,
        "frequency": frequency,
        "case_id": case_id,
        "case_name": case_name
    }
    
    debug_info = None
    if os.getenv("DEBUG_CALC", "0") == "1":
        debug_info = {
            "validation_checks": {
                "frequency_supported": frequency == "monthly",
                "scenario_count": len(scenario_ids)
            }
        }
    
    # ולידציה בסיסית
    if frequency != "monthly":
        log_calc("compare_scenarios_error", payload, None, {"error": "Invalid frequency"})
        raise ValueError("Only 'monthly' is supported")

    # הפקת תזרים עבור כל תרחיש - פורמט חדש במערך
    scenarios_out = []
    
    for sid in scenario_ids:
        # משתמש בפונקציה הקיימת שמחזירה רשת מלאה
        monthly = generate_cashflow(db_session, client_id, sid, from_yyyymm, to_yyyymm, case_id=case_id)
        
        # נורמליזציה של שדות והבטחת אחידות
        norm_monthly = []
        for r in monthly:
            # תאריך כמחרוזת YYYY-MM-01
            date_str = r.get('date')
            if isinstance(date_str, (datetime, date)):
                date_str = date_str.strftime('%Y-%m-01')  # normalized monthly anchor
            elif isinstance(date_str, str) and len(date_str) >= 8:
                date_str = date_str[:7] + "-01"  # ensure DD is 01 for monthly anchor
            
            # שדות מספריים - וידוא שקיימים ומספריים
            inflow = float(r.get('inflow') or 0)
            outflow = float(r.get('outflow') or 0)
            add_net = float(r.get('additional_income_net') or 0)
            cap_net = float(r.get('capital_return_net') or 0)
            
            # חישוב מחדש של net לעקביות
            net = inflow - outflow + add_net + cap_net
            
            # הוספה למערך המנורמל
            norm_monthly.append({
                'date': date_str,
                'inflow': round(inflow, 2),
                'outflow': round(outflow, 2),
                'additional_income_net': round(add_net, 2),
                'capital_return_net': round(cap_net, 2),
                'net': round(net, 2)
            })
        
        # קיבוץ לפי שנה וחישוב סיכומים שנתיים
        yearly = {}
        for row in norm_monthly:
            year = row['date'][:4]  # extract YYYY
            if year not in yearly:
                yearly[year] = []
            yearly[year].append(row)
        
        # חישוב סיכומים שנתיים
        yearly_totals = {}
        for year, rows in yearly.items():
            yearly_totals[year] = _compute_yearly_from_months(rows)
        
        # הוספה לרשימת התרחישים בפורמט החדש
        scenarios_out.append({
            'scenario_id': sid,
            'monthly': norm_monthly,
            'yearly_totals': yearly_totals
        })
    
    # בניית תשובה סופית בפורמט החדש
    result = {
        'scenarios': scenarios_out,
        'meta': {
            'client_id': client_id,
            'from': from_yyyymm,
            'to': to_yyyymm,
            'frequency': frequency,
            'case': {
                'id': case_id,
                'name': case_name,
                'reasons': case_reasons
            }
        }
    }
    
    # Logical validation checks on new format
    _validate_scenario_results_new(result)
    
    # Log successful completion
    log_calc("compare_scenarios", payload, result, debug_info)
    return result


def _validate_scenario_results_new(result: Dict[str, Any]):
    """
    Validate scenario comparison results for logical consistency with new format
    Checks for negative taxes, extreme values, etc.
    """
    warnings = []
    
    for scenario in result.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        yearly_data = scenario.get("yearly_totals", {})
        
        # Check month count
        monthly_data = scenario.get("monthly", [])
        month_count = len(monthly_data)
        if month_count < 12:
            warnings.append(f"Scenario {scenario_id}: Only {month_count}/12 months available")
        
        # Check yearly totals
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
            
            # Verify that net is consistent with components
            computed_net = (
                totals.get("inflow", 0) - 
                totals.get("outflow", 0) + 
                totals.get("additional_income_net", 0) + 
                totals.get("capital_return_net", 0)
            )
            if abs(computed_net - net) > 0.02:  # Allow small rounding difference
                warnings.append(f"Scenario {scenario_id}, Year {year}: Net inconsistency. Reported: {net}, Computed: {computed_net}")
    
    # Log warnings if any
    if warnings:
        log_calc("validation_warnings", {"scenario_count": len(result.get("scenarios", []))}, warnings)


def _validate_scenario_results(result: Dict[str, Any]):
    """
    Legacy validation function for old format.
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
