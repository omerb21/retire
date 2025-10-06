from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import os

from sqlalchemy.orm import Session


# Import the actual function from the calculation module
from app.calculation.income_integration import integrate_all_incomes_with_scenario
from app.utils.calculation_log import log_calc
from app.services.case_service import detect_case


def _parse_year_month(ym: str) -> Tuple[int, int]:
    if not isinstance(ym, str) or len(ym) != 7 or ym[4] != "-":
        raise ValueError("Month must be 'YYYY-MM'")
    y = int(ym[0:4])
    m = int(ym[5:7])
    if not (1 <= m <= 12):
        raise ValueError("Month must be 01..12")
    return y, m


def _parse_ym(ym: str) -> date:
    """Convert YYYY-MM string to date object (first day of month)"""
    y, m = map(int, ym.split("-"))
    return date(y, m, 1)


def _add_month(d: date) -> date:
    """Add one month to date"""
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _first_of_month(ym: str) -> date:
    y, m = _parse_year_month(ym)
    return date(y, m, 1)


def _month_iter(start_ym: str, end_ym: str) -> List[date]:
    """Inclusive month range as first-of-month dates."""
    sy, sm = _parse_year_month(start_ym)
    ey, em = _parse_year_month(end_ym)
    d = date(sy, sm, 1)
    end_d = date(ey, em, 1)
    out: List[date] = []
    while d <= end_d:
        out.append(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return out


def generate_cashflow(
    db: Session,
    client_id: int,
    scenario_id: int,
    start_ym: str,
    end_ym: str,
    frequency: str = "monthly",
    case_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    # Auto-detect case if not provided
    if case_id is None:
        case_detection_result = detect_case(db, client_id)
        case_id = case_detection_result.case_id
    
    # Log calculation start
    payload = {
        "client_id": client_id,
        "scenario_id": scenario_id,
        "start_ym": start_ym,
        "end_ym": end_ym,
        "frequency": frequency,
        "case_id": case_id
    }
    
    debug_info = None
    if os.getenv("DEBUG_CALC", "0") == "1":
        debug_info = {
            "validation_checks": {
                "frequency_supported": frequency == "monthly",
                "date_range_valid": start_ym <= end_ym
            }
        }
    
    if frequency != "monthly":
        log_calc("generate_cashflow_error", payload, None, {"error": "Invalid frequency"})
        raise ValueError("supported: monthly")
    
    # Validate date range
    if start_ym > end_ym:
        log_calc("generate_cashflow_error", payload, None, {"error": "Invalid date range"})
        raise ValueError("'from' date must be less than or equal to 'to' date")

    months = _month_iter(start_ym, end_ym)
    results: List[Dict[str, Any]] = []

    for month_d in months:
        # בסיס: שורה ריקה (0) לאותו חודש
        scenario_cashflow = [{
            "date": month_d,
            "inflow": 0,
            "outflow": 0,
            "net": 0,
        }]

        # שימוש בלוגיקה הקיימת של אינטגרציה (כמו endpoint integrate-all)
        enriched = integrate_all_incomes_with_scenario(
            db_session=db,
            client_id=client_id,
            scenario_cashflow=scenario_cashflow,
            reference_date=month_d,
        )

        # מצופה ש-enriched מחזיר מערך עם אותה שורה מועשרת
        # אם אין נתונים, ניצור שורה ריקה במקום לדלג
        if not enriched:
            row = {
                "date": month_d,
                "inflow": 0,
                "outflow": 0,
                "additional_income_net": 0,
                "capital_return_net": 0,
                "net": 0,
                "meta": {"is_empty_month": True}
            }
        else:
            row = enriched[0]

        # Ensure all required fields exist and are numeric
        inflow = float(row.get("inflow", 0) or 0)
        outflow = float(row.get("outflow", 0) or 0)
        add_net = float(row.get("additional_income_net", 0) or 0)
        cap_net = float(row.get("capital_return_net", 0) or 0)
        
        # Recalculate net with all components for consistency
        row["inflow"] = inflow
        row["outflow"] = outflow
        row["additional_income_net"] = add_net
        row["capital_return_net"] = cap_net
        row["net"] = inflow - outflow + add_net + cap_net
        
        # Apply case-specific logic
        final_tax = True  # Default for most cases
        
        # Case-specific modifications
        if case_id in [1, 2, 3]:  # Cases 1-3: No current employer integration
            # For these cases, don't include current employer calculations if they exist
            # The integrate_all function handles this already since it works with what's in DB
            pass
        elif case_id == 4:  # Case 4: Active employment with no leave
            final_tax = False  # No final tax liability on retirement grants
        elif case_id == 5:  # Case 5: Regular with leave (default full scenario)
            # Use existing behavior for Case 5
            pass
            
        # Add meta information about the case
        if "meta" not in row:
            row["meta"] = {}
        row["meta"]["case_id"] = case_id
        row["meta"]["final_tax"] = final_tax
        
        results.append(row)
    
    # Ensure full month grid with exactly 12 months per year
    results = ensure_full_month_grid(results, start_ym, end_ym)

    # Log successful completion
    log_calc("generate_cashflow", payload, results, debug_info)
    
    # Explicitly log the number of months returned
    month_count = len(results)
    year_month_range = f"{start_ym}..{end_ym}"
    log_calc("generate_cashflow_stats", {"month_count": month_count, "range": year_month_range}, None)
    
    return results


def ensure_full_month_grid(rows: list[dict], from_ym: str, to_ym: str) -> list[dict]:
    """Ensure all months from from_ym to to_ym are present in the data"""
    # Create mapping of existing data by year-month
    by_ym = {}
    for r in rows:
        # Normalize date to YYYY-MM string
        dstr = str(r["date"])
        ym = dstr[:7] if len(dstr) >= 7 else dstr
        
        # Extract values, ensure they're numeric
        inflow = float(r.get("inflow", 0) or 0)
        outflow = float(r.get("outflow", 0) or 0)
        add_net = float(r.get("additional_income_net", 0) or 0)
        cap_net = float(r.get("capital_return_net", 0) or 0)
        
        # Always recalculate net for consistency
        net = inflow - outflow + add_net + cap_net
        
        # Copy any meta information
        meta = r.get("meta", {})
        
        by_ym[ym] = {
            "date": f"{ym}-01",  # Always string format YYYY-MM-01
            "inflow": inflow,
            "outflow": outflow,
            "additional_income_net": add_net,
            "capital_return_net": cap_net,
            "net": net,
            "meta": meta
        }

    # Generate complete month grid
    out = []
    cur = _parse_ym(from_ym)
    end = _parse_ym(to_ym)
    while cur <= end:
        ym = f"{cur.year:04d}-{cur.month:02d}"
        if ym in by_ym:
            out.append(by_ym[ym])
        else:
            # Create zero-filled row with consistent net calculation
            inflow = 0
            outflow = 0
            add_net = 0
            cap_net = 0
            net = inflow - outflow + add_net + cap_net
            
            out.append({
                "date": f"{ym}-01",  # Always string format
                "inflow": inflow, 
                "outflow": outflow,
                "additional_income_net": add_net,
                "capital_return_net": cap_net,
                "net": net,
                "meta": {"is_filled": True}  # Mark as grid-filled month
            })
        cur = _add_month(cur)
    return out
