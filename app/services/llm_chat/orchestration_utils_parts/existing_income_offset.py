from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome
from app.models.client import Client
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.services.additional_income_service import AdditionalIncomeService


def compute_existing_income_offset_monthly(
    *,
    db: Session,
    client_id: int,
    target_is_net: bool,
    reference_date: date | None = None,
) -> float:
    if reference_date is None:
        today = date.today()
        reference_date = date(today.year, today.month, 1)

    try:
        incomes = (
            db.query(AdditionalIncome)
            .filter(AdditionalIncome.client_id == client_id)
            .all()
        )
    except Exception:
        incomes = []

    if not incomes:
        return 0.0

    try:
        client = db.query(Client).filter(Client.id == client_id).first()
    except Exception:
        client = None

    income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())

    gross_total = Decimal("0")
    net_total = Decimal("0")

    for income in incomes or []:
        try:
            if income.start_date and reference_date < income.start_date:
                continue
            if income.end_date and reference_date > income.end_date:
                continue
        except Exception:
            pass

        try:
            monthly_gross = income_service.calculate_monthly_amount(income)
        except Exception:
            continue

        try:
            tax_amount, _include_in_total = income_service.calculate_tax(
                monthly_gross,
                income,
                client,
                reference_date,
            )
        except Exception:
            tax_amount = Decimal("0")

        monthly_net = monthly_gross - tax_amount

        gross_total += monthly_gross
        net_total += monthly_net

    try:
        out = net_total if target_is_net else gross_total
        return float(out)
    except Exception:
        return 0.0


def apply_income_offset_to_target(
    db: Session, client_id: int, target_net: float
) -> tuple[float, float]:
    """Returns (offset_net, effective_target_net)."""
    try:
        requested = float(target_net or 0)
    except Exception:
        requested = 0.0

    offset_net = compute_existing_income_offset_monthly(
        db=db,
        client_id=client_id,
        target_is_net=True,
    )
    try:
        effective = max(float(requested) - float(offset_net), 0.0)
    except Exception:
        effective = 0.0
    return float(offset_net or 0.0), float(effective)
