from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from app.services.simulation_engine.models import SimulationRequest


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def _to_float_2(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _is_active_in_month(
    *, start: Optional[date], end: Optional[date], month: date
) -> bool:
    m = _first_of_month(month)
    if start is not None and _first_of_month(start) > m:
        return False
    if end is not None and _first_of_month(end) < m:
        return False
    return True


@dataclass(frozen=True)
class MinimalComputation:
    monthly_cashflow: list[dict[str, Any]]
    tax_breakdown: dict[str, Any]
    sustainability_metrics: dict[str, Any]
    exempt_pension_component: dict[str, float]
    raw_calculation_map: dict[str, Any]


def compute_from_snapshot(snapshot: dict, request: SimulationRequest) -> dict:
    """Pure computation from snapshot + request.

    No DB/session usage allowed.

    Stage 2 minimal output:
    - monthly cashflow aggregation of PensionFund.pension_amount + AdditionalIncome (monthly only)
    """

    month0 = _first_of_month(request.retirement_date)
    months = [_add_months(month0, i) for i in range(12)]

    pf_items = snapshot.get("pension_funds") or []
    ai_items = snapshot.get("additional_incomes") or []

    monthly_cashflow: list[dict[str, Any]] = []

    for m in months:
        pf_total = 0.0
        for pf in pf_items:
            if (pf.get("record_status") or "active") != "active":
                continue
            start = pf.get("pension_start_date")
            if not _is_active_in_month(start=start, end=None, month=m):
                continue
            pf_total += _to_float_2(pf.get("pension_amount"))

        ai_total = 0.0
        for inc in ai_items:
            if (inc.get("frequency") or "").lower() != "monthly":
                continue
            start = inc.get("start_date")
            end = inc.get("end_date")
            if not _is_active_in_month(start=start, end=end, month=m):
                continue
            ai_total += _to_float_2(inc.get("amount"))

        gross = _to_float_2(pf_total + ai_total)
        net = gross

        components = {
            "pension_funds": _to_float_2(pf_total),
            "additional_incomes": _to_float_2(ai_total),
        }
        monthly_cashflow.append(
            {
                "month": m,
                "gross": gross,
                "net": net,
                "components": components,
            }
        )

    raw_calculation_map = {
        "client_id": snapshot.get("client", {}).get("id"),
        "cashflow_months": len(monthly_cashflow),
        "pension_funds_count": len(pf_items),
        "additional_incomes_count": len(ai_items),
        "gross_month0": monthly_cashflow[0]["gross"] if monthly_cashflow else None,
    }

    return MinimalComputation(
        monthly_cashflow=monthly_cashflow,
        tax_breakdown={
            "taxable_income_monthly": None,
            "tax_monthly": None,
            "notes": [],
        },
        sustainability_metrics={
            "is_sustainable": None,
            "depletion_month": None,
            "notes": [],
        },
        exempt_pension_component={},
        raw_calculation_map=raw_calculation_map,
    ).__dict__
