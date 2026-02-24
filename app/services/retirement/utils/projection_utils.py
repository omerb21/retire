from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Union

DEFAULT_NET_ANNUAL_RATE = 0.03
DAYS_IN_YEAR = 365.25

Number = Union[int, float, Decimal]


def calculate_compound_factor(
    *,
    from_date: Optional[date],
    to_date: Optional[date],
    annual_rate: float = DEFAULT_NET_ANNUAL_RATE,
) -> float:
    if not from_date or not to_date:
        return 1.0

    days = (to_date - from_date).days
    if days <= 0:
        return 1.0

    years = days / DAYS_IN_YEAR
    return (1.0 + float(annual_rate)) ** years


def project_amount(
    *,
    amount: Number,
    from_date: Optional[date],
    to_date: Optional[date],
    annual_rate: float = DEFAULT_NET_ANNUAL_RATE,
) -> float:
    try:
        base = float(amount or 0)
    except (TypeError, ValueError):
        base = 0.0

    factor = calculate_compound_factor(
        from_date=from_date,
        to_date=to_date,
        annual_rate=annual_rate,
    )
    return base * factor
