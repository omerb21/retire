from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from app.models.pension_fund import PensionFund


def compute_monthly_pension_summary(
    session: Session, client_id: int, today: date
) -> dict[str, Any]:
    def _to_decimal(value: object) -> Decimal:
        try:
            if value is None:
                return Decimal("0")
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _round2(value: Decimal) -> float:
        try:
            return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        except Exception:
            try:
                return float(value)
            except Exception:
                return 0.0

    rows: list[PensionFund] = (
        session.query(PensionFund)
        .filter(PensionFund.client_id == int(client_id))
        .filter(PensionFund.fund_type == "monthly_pension")
        .filter(PensionFund.record_status == "active")
        .filter(PensionFund.pension_amount.isnot(None))
        .filter(PensionFund.pension_amount > 0)
        .order_by(PensionFund.id.asc())
        .all()
    )

    current_items: list[dict[str, Any]] = []
    future_items: list[dict[str, Any]] = []

    current_sum = Decimal("0")
    future_sum = Decimal("0")
    current_taxable_sum = Decimal("0")
    current_exempt_sum = Decimal("0")

    for r in rows:
        start_date = getattr(r, "pension_start_date", None)
        is_future = bool(start_date and start_date > today)
        tax_treatment = (
            getattr(r, "tax_treatment", None) or "taxable"
        ).strip() or "taxable"
        amount_raw = getattr(r, "pension_amount", None)
        amount = _to_decimal(amount_raw)

        item = {
            "id": int(getattr(r, "id", 0) or 0),
            "amount": float(amount),
            "start_date": start_date.isoformat() if start_date else None,
            "tax_treatment": tax_treatment,
        }

        if is_future:
            future_items.append(item)
            future_sum += amount
        else:
            current_items.append(item)
            current_sum += amount

            tt_lower = tax_treatment.strip().lower()
            if tt_lower == "exempt":
                current_exempt_sum += amount
            elif tt_lower == "taxable":
                current_taxable_sum += amount

    def _filter_tax(items: list[dict[str, Any]], wanted: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for it in items:
            raw = str(it.get("tax_treatment") or "").strip().lower()
            if raw == wanted:
                out.append(it)
        return out

    current_taxable_items = _filter_tax(current_items, "taxable")
    current_exempt_items = _filter_tax(current_items, "exempt")

    total_sum = current_sum + future_sum

    return {
        "client_id": int(client_id),
        "today": today.isoformat(),
        "monthly_pension": {
            "current": {
                "count": int(len(current_items)),
                "sum": _round2(current_sum),
                "taxable": {
                    "count": int(len(current_taxable_items)),
                    "sum": _round2(current_taxable_sum),
                },
                "exempt": {
                    "count": int(len(current_exempt_items)),
                    "sum": _round2(current_exempt_sum),
                },
                "items": current_items,
            },
            "future": {
                "count": int(len(future_items)),
                "sum": _round2(future_sum),
                "items": future_items,
            },
            "total": {
                "count": int(len(current_items) + len(future_items)),
                "sum": _round2(total_sum),
            },
        },
    }
