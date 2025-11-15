"""High-level calculation API for Results screen.

This router exposes a simple endpoint that returns a CalculationResult
structure used by the frontend Results.tsx screen. It is intentionally
thin and delegates the heavy lifting to the cashflow_service and
case_detection logic.
"""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.calculation_result import (
    CalculationCashFlowItem,
    CalculationRequest,
    CalculationResult,
    CalculationSummary,
)
from app.services.cashflow_service import generate_cashflow
from app.services.case_service import detect_case


router = APIRouter(
    prefix="/api/v1",
    tags=["calc"],
)


@router.post(
    "/calculation/run",
    response_model=CalculationResult,
    status_code=status.HTTP_200_OK,
    summary="Run high-level cashflow calculation for Results screen",
)
def run_calculation(
    body: CalculationRequest,
    db: Session = Depends(get_db),
) -> CalculationResult:
    """Run a high-level cashflow calculation for a client.

    The endpoint uses the unified cashflow_service (which already integrates
    additional incomes and capital assets) and wraps the monthly rows into
    the CalculationResult structure consumed by the frontend Results.tsx.

    Note: At this stage the gross/tax breakdown focuses on non-pension
    income sources (additional incomes and capital assets). Pension flows
    can be integrated later without breaking this contract.
    """

    # Detect client case so we can return a consistent case_number
    try:
        case_detection = detect_case(db, body.client_id)
        case_id = case_detection.case_id
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Determine default calculation horizon: 24 months starting this month
    today = date.today()
    start_ym = f"{today.year:04d}-{today.month:02d}"
    total_months = 24
    end_year = today.year + (today.month - 1 + total_months - 1) // 12
    end_month = ((today.month - 1 + total_months - 1) % 12) + 1
    end_ym = f"{end_year:04d}-{end_month:02d}"

    # Generate monthly cashflow rows using the shared service
    try:
        raw_rows = generate_cashflow(
            db=db,
            client_id=body.client_id,
            scenario_id=body.scenario_id or 0,
            start_ym=start_ym,
            end_ym=end_ym,
            frequency="monthly",
            case_id=case_id,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cashflow: {e}",
        )

    cash_flow: List[CalculationCashFlowItem] = []
    total_gross = 0.0
    total_tax = 0.0
    total_net = 0.0

    for row in raw_rows:
        # Extract year/month from date (can be date or string)
        d = row.get("date")
        if hasattr(d, "year") and hasattr(d, "month"):
            year = int(d.year)
            month = int(d.month)
        else:
            s = str(d)
            year = int(s[0:4]) if len(s) >= 4 else today.year
            month = int(s[5:7]) if len(s) >= 7 else 1

        # Non-pension gross/tax components (already provided by integration layer)
        add_gross = float(row.get("additional_income_gross", 0) or 0)
        cap_gross = float(row.get("capital_return_gross", 0) or 0)
        add_tax_total = float(
            row.get("additional_income_tax_for_total", row.get("additional_income_tax", 0))
            or 0
        )
        cap_tax = float(row.get("capital_return_tax", 0) or 0)
        net_value = float(row.get("net", 0) or 0)

        gross_income = add_gross + cap_gross
        tax_amount = add_tax_total + cap_tax

        total_gross += gross_income
        total_tax += tax_amount
        total_net += net_value

        cash_flow.append(
            CalculationCashFlowItem(
                year=year,
                month=month,
                gross_income=gross_income,
                tax_amount=tax_amount,
                net_income=net_value,
                asset_balances={},
            )
        )

    summary = CalculationSummary(
        total_gross=total_gross,
        total_tax=total_tax,
        total_net=total_net,
        final_balances={},
    )

    assumptions = {
        "from": start_ym,
        "to": end_ym,
        "frequency": "monthly",
        "case": {
            "id": case_id,
            "name": getattr(case_detection, "case_name", None),
            "reasons": getattr(case_detection, "reasons", []),
        },
    }

    return CalculationResult(
        client_id=body.client_id,
        scenario_name=body.scenario_name,
        case_number=case_id,
        assumptions=assumptions,
        cash_flow=cash_flow,
        summary=summary,
    )
