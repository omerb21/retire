from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import json
import logging
from app.database import get_db
from app.models.pension_fund import PensionFund
from app.schemas.pension_fund import (
    PensionFundCreate,
    PensionFundUpdate,
    PensionFundOut,
)
from app.services.pension_fund_service import (
    compute_and_persist,
    compute_and_persist_fund,
    compute_all_pension_funds,
)
from app.services.retirement.utils.projection_utils import calculate_compound_factor

router = APIRouter(prefix="/api/v1", tags=["pension-funds"])
logger = logging.getLogger("app.pension_fund")


def _validate_monthly_pension_invariant(
    fund_type: str | None,
    record_status: str | None,
    pension_amount: float | None,
) -> None:
    """Raise 400 if an *active* monthly_pension has pension_amount <= 0."""
    if fund_type != "monthly_pension":
        return
    if (record_status or "active") != "active":
        return
    try:
        amt = float(pension_amount) if pension_amount is not None else 0.0
    except (TypeError, ValueError):
        amt = 0.0
    if amt <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "monthly_pension פעילה חייבת לכלול pension_amount > 0",
                "code": "MONTHLY_PENSION_ZERO_AMOUNT",
            },
        )


@router.post(
    "/clients/{client_id}/pension-funds",
    response_model=PensionFundOut,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/clients/{client_id}/pension-funds/",
    response_model=PensionFundOut,
    status_code=status.HTTP_201_CREATED,
)
def create_pension_fund(
    client_id: int, payload: PensionFundCreate, db: Session = Depends(get_db)
):
    if payload.client_id != client_id:
        raise HTTPException(status_code=422, detail={"error": "client_id mismatch"})

    logger.info("Create pension fund request received (client_id=%s)", client_id)
    logger.debug("Create pension fund payload: %s", payload.model_dump())
    data = payload.model_dump()

    try:
        src_raw = data.get("conversion_source")
        if src_raw:
            src = json.loads(src_raw)
            if isinstance(src, dict):
                src_type = src.get("type") or src.get("source")
                start_date = data.get("pension_start_date")
                if (
                    src_type == "pension_portfolio"
                    and isinstance(start_date, date)
                    and start_date > date.today()
                ):
                    factor = calculate_compound_factor(
                        from_date=date.today(), to_date=start_date
                    )
                    balance = data.get("balance")
                    if balance is not None:
                        data["balance"] = float(balance) * float(factor)
                        annuity_factor = data.get("annuity_factor")
                        try:
                            af = (
                                float(annuity_factor)
                                if annuity_factor is not None
                                else 0.0
                            )
                        except (TypeError, ValueError):
                            af = 0.0
                        if af > 0:
                            data["pension_amount"] = float(data["balance"] or 0) / af
    except Exception:
        pass

    fund = PensionFund(**data)
    logger.debug(
        "Create pension fund before commit (balance=%s, input_mode=%s)",
        fund.balance,
        fund.input_mode,
    )

    # API-level invariant: reject active monthly_pension with pension_amount <= 0
    _validate_monthly_pension_invariant(
        fund_type=data.get("fund_type"),
        record_status=data.get("record_status", "active"),
        pension_amount=data.get("pension_amount"),
    )

    # אל תאפס את ה-balance! זה קריטי להיוון!
    if fund.input_mode == "calculated" and fund.balance:
        logger.debug(
            "Create pension fund calculated mode - preserving balance=%s", fund.balance
        )

    db.add(fund)
    db.commit()
    db.refresh(fund)
    logger.debug(
        "Create pension fund after refresh (id=%s, balance=%s)", fund.id, fund.balance
    )
    return fund


@router.get("/pension-funds/{fund_id}", response_model=PensionFundOut)
def get_pension_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    return fund


@router.put("/pension-funds/{fund_id}", response_model=PensionFundOut)
def update_pension_fund(
    fund_id: int, payload: PensionFundUpdate, db: Session = Depends(get_db)
):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(fund, k, v)

    # API-level invariant: reject active monthly_pension with pension_amount <= 0
    _validate_monthly_pension_invariant(
        fund_type=getattr(fund, "fund_type", None),
        record_status=getattr(fund, "record_status", "active"),
        pension_amount=getattr(fund, "pension_amount", None),
    )

    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


@router.delete("/pension-funds/{fund_id}", status_code=status.HTTP_200_OK)
def delete_pension_fund(fund_id: int, db: Session = Depends(get_db)):
    from app.services.asset_deletion_service import delete_pension_fund_with_restoration

    result = delete_pension_fund_with_restoration(db, fund_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail={"error": result["error"]})

    db.commit()
    return result


@router.delete(
    "/clients/{client_id}/pension-funds/{fund_id}", status_code=status.HTTP_200_OK
)
@router.delete(
    "/clients/{client_id}/pension-funds/{fund_id}/", status_code=status.HTTP_200_OK
)
def delete_client_pension_fund(
    client_id: int, fund_id: int, db: Session = Depends(get_db)
):
    from app.services.asset_deletion_service import delete_pension_fund_with_restoration

    result = delete_pension_fund_with_restoration(db, fund_id, client_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail={"error": result["error"]})

    db.commit()
    return result


@router.post("/pension-funds/{fund_id}/compute", response_model=PensionFundOut)
def compute_pension_fund(
    fund_id: int, reference_date: Optional[date] = None, db: Session = Depends(get_db)
):
    try:
        fund = compute_and_persist_fund(db, fund_id)
        return fund
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})


@router.post(
    "/clients/{client_id}/pension-funds/{fund_id}/compute",
    response_model=PensionFundOut,
)
@router.post(
    "/clients/{client_id}/pension-funds/{fund_id}/compute/",
    response_model=PensionFundOut,
)
def compute_client_pension_fund(
    client_id: int,
    fund_id: int,
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    try:
        fund = db.get(PensionFund, fund_id)
        if not fund:
            raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
        if fund.client_id != client_id:
            raise HTTPException(
                status_code=404, detail={"error": "מקור קצבה לא נמצא עבור לקוח זה"}
            )

        fund = compute_and_persist_fund(db, fund_id)
        return fund
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})


@router.post(
    "/clients/{client_id}/pension-funds/compute-all",
    response_model=List[PensionFundOut],
)
@router.post(
    "/clients/{client_id}/pension-funds/compute-all/",
    response_model=List[PensionFundOut],
)
def compute_all_client_pension_funds(
    client_id: int, reference_date: Optional[date] = None, db: Session = Depends(get_db)
):
    """Compute all pension funds for a client"""
    # Check if client exists
    from app.models.client import Client

    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})

    # Get all pension funds for the client
    funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
    if not funds:
        return []

    # Compute and update all funds
    updated_funds = []
    for fund in funds:
        updated_fund = compute_and_persist(db, fund, reference_date)
        updated_funds.append(updated_fund)

    return updated_funds


@router.get("/clients/{client_id}/pension-funds", response_model=List[PensionFundOut])
@router.get("/clients/{client_id}/pension-funds/", response_model=List[PensionFundOut])
def get_client_pension_funds(client_id: int, db: Session = Depends(get_db)):
    """Get all pension funds for a client - FAST VERSION"""
    try:
        funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
        logger.debug(
            "Get pension funds (client_id=%s, count=%s)", client_id, len(funds)
        )
        for fund in funds:
            logger.debug(
                "Pension fund row (id=%s, balance=%s, input_mode=%s)",
                fund.id,
                fund.balance,
                fund.input_mode,
            )
        return funds
    except Exception as e:
        logger.exception(
            "Error getting pension funds for client_id=%s: %s", client_id, e
        )
        return []
