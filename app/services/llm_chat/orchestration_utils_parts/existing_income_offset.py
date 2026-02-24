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


# ---------------------------------------------------------------------------
# Unified target breakdown – single source of truth for ALL paths
# ---------------------------------------------------------------------------


class TargetPlanBreakdown:
    """Immutable breakdown of the user's desired target into plan-level target.

    Semantics
    ---------
    desired_net_total
        The raw number the user typed ("30000 נטו").
    other_income_offset_net
        Monthly net from AdditionalIncome records (non-pension income).
    other_income_offset_gross
        Monthly gross from AdditionalIncome records.
    effective_plan_target
        What BUILD_TARGET_PENSION_PLAN should receive as
        ``target_monthly_pension``.  Equals
        ``desired_net_total − other_income_offset`` (net or gross
        depending on *target_is_net*).
    target_is_net
        Whether the user asked for a net target.
    """

    __slots__ = (
        "desired_net_total",
        "target_is_net",
        "other_income_offset_net",
        "other_income_offset_gross",
        "effective_plan_target",
    )

    def __init__(
        self,
        *,
        desired_net_total: float,
        target_is_net: bool,
        other_income_offset_net: float,
        other_income_offset_gross: float,
        effective_plan_target: float,
    ):
        self.desired_net_total = desired_net_total
        self.target_is_net = target_is_net
        self.other_income_offset_net = other_income_offset_net
        self.other_income_offset_gross = other_income_offset_gross
        self.effective_plan_target = effective_plan_target

    def to_dict(self) -> dict:
        return {
            "desired_net_total": self.desired_net_total,
            "target_is_net": self.target_is_net,
            "other_income_offset_net": self.other_income_offset_net,
            "other_income_offset_gross": self.other_income_offset_gross,
            "effective_plan_target": self.effective_plan_target,
        }


def compute_effective_plan_target(
    *,
    db: Session,
    client_id: int,
    desired_total: float,
    target_is_net: bool,
) -> TargetPlanBreakdown:
    """Compute the effective target to pass to BUILD_TARGET_PENSION_PLAN.

    This is the **single** function that both the deterministic-stream path
    and the tool-call-loop path must call so that the same offsets are
    applied regardless of routing.

    Only *AdditionalIncome* (other income) is subtracted here.
    Existing-pension offsets are handled inside the adapter
    (``target_plan.py``) which already queries ``compute_monthly_pension_summary``
    and subtracts existing pensions from the gross requirement.
    """
    try:
        desired = float(desired_total or 0)
    except Exception:
        desired = 0.0

    other_income_offset_net = 0.0
    other_income_offset_gross = 0.0
    try:
        other_income_offset_net = compute_existing_income_offset_monthly(
            db=db,
            client_id=client_id,
            target_is_net=True,
        )
    except Exception:
        other_income_offset_net = 0.0
    try:
        other_income_offset_gross = compute_existing_income_offset_monthly(
            db=db,
            client_id=client_id,
            target_is_net=False,
        )
    except Exception:
        other_income_offset_gross = 0.0

    if target_is_net:
        offset = float(other_income_offset_net)
    else:
        offset = float(other_income_offset_gross)

    effective = max(desired - offset, 0.0)

    return TargetPlanBreakdown(
        desired_net_total=desired,
        target_is_net=target_is_net,
        other_income_offset_net=other_income_offset_net,
        other_income_offset_gross=other_income_offset_gross,
        effective_plan_target=effective,
    )
