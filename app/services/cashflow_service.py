from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import os

from sqlalchemy.orm import Session


# Import the actual function from the calculation module
from app.calculation.income_integration import integrate_all_incomes_with_scenario
from app.utils.calculation_log import log_calc


def _parse_year_month(ym: str) -> Tuple[int, int]:
    if not isinstance(ym, str) or len(ym) != 7 or ym[4] != "-":
        raise ValueError("Month must be 'YYYY-MM'")
    y = int(ym[0:4])
    m = int(ym[5:7])
    if not (1 <= m <= 12):
        raise ValueError("Month must be 01..12")
    return y, m


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
) -> List[Dict[str, Any]]:
    # Log calculation start
    payload = {
        "client_id": client_id,
        "scenario_id": scenario_id,
        "start_ym": start_ym,
        "end_ym": end_ym,
        "frequency": frequency
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
        if not enriched:
            continue
        row = enriched[0]

        inflow = float(row.get("inflow", 0))
        outflow = float(row.get("outflow", 0))
        add_net = float(row.get("additional_income_net", 0))
        cap_net = float(row.get("capital_return_net", 0))

        results.append(row)

    # Log successful completion
    log_calc("generate_cashflow", payload, results, debug_info)
    return results
