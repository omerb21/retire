"""API router for income and asset integration with scenario cashflow."""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.calculation.income_integration import (
    integrate_additional_incomes_with_scenario,
    integrate_capital_assets_with_scenario,
    integrate_all_incomes_with_scenario,
)
from app.schemas.cashflow import (
    CashflowEnvelope,
    MonthlyCashflowItem,
    ScenarioCashflowItem,
)

logger = logging.getLogger("app.income_integration")

router = APIRouter(prefix="/clients/{client_id}/cashflow", tags=["cashflow-integration"])


@router.post("/integrate-incomes", response_model=List[Dict[str, Any]])
def integrate_incomes_with_cashflow(
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = Query(None, description="Reference date for calculations"),
    db: Session = Depends(get_db)
):
    """
    Integrate additional incomes with scenario cashflow.
    
    Args:
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with additional income integrated
    """
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    # Validate scenario cashflow format
    if not scenario_cashflow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario cashflow cannot be empty"
        )
    
    # Validate required fields in scenario cashflow
    required_fields = ['date', 'inflow', 'outflow', 'net']
    for i, item in enumerate(scenario_cashflow):
        for field in required_fields:
            if field not in item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field '{field}' in scenario cashflow item {i}"
                )
    
    try:
        # Convert date strings to date objects if needed
        for item in scenario_cashflow:
            if isinstance(item['date'], str):
                item['date'] = date.fromisoformat(item['date'])
        
        integrated_cashflow = integrate_additional_incomes_with_scenario(
            db, client_id, scenario_cashflow, reference_date
        )
        
        return integrated_cashflow
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error integrating additional incomes: {str(e)}"
        )


@router.post("/integrate-assets", response_model=List[Dict[str, Any]])
def integrate_assets_with_cashflow(
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = Query(None, description="Reference date for calculations"),
    db: Session = Depends(get_db)
):
    """
    Integrate capital assets with scenario cashflow.
    
    Args:
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with capital asset returns integrated
    """
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    # Validate scenario cashflow format
    if not scenario_cashflow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario cashflow cannot be empty"
        )
    
    # Validate required fields in scenario cashflow
    required_fields = ['date', 'inflow', 'outflow', 'net']
    for i, item in enumerate(scenario_cashflow):
        for field in required_fields:
            if field not in item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field '{field}' in scenario cashflow item {i}"
                )
    
    try:
        # Convert date strings to date objects if needed
        for item in scenario_cashflow:
            if isinstance(item['date'], str):
                item['date'] = date.fromisoformat(item['date'])
        
        integrated_cashflow = integrate_capital_assets_with_scenario(
            db, client_id, scenario_cashflow, reference_date
        )
        
        return integrated_cashflow
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error integrating capital assets: {str(e)}"
        )


@router.post(
    "/integrate-all",
    response_model=List[Dict[str, Any]],
    summary="Integrate all income sources with scenario cashflow",
    description=(
        "Accepts **either** a JSON array of ScenarioCashflowItem "
        "(date/inflow/outflow/net) **or** a CashflowEnvelope object "
        "with a `monthly` list (date/income/expenses/net) as returned "
        "by GET …/cashflow."
    ),
)
def integrate_all_with_cashflow(
    client_id: int,
    request: Request,
    payload: Union[List[ScenarioCashflowItem], CashflowEnvelope] = Body(...),
    reference_date: Optional[date] = Query(None, description="Reference date for calculations"),
    db: Session = Depends(get_db),
):
    """
    Integrate both additional incomes and capital assets with scenario cashflow.

    Accepts two payload formats:
    1. **List format** – ``[{date, inflow, outflow, net}, …]``
    2. **Envelope format** – ``{monthly: [{date, income, expenses, net}, …], …}``
       The envelope is normalised to the list format automatically.
    """
    # ── resolve trace_id for logging (best-effort) ──
    trace_id: Optional[str] = None
    try:
        from app.utils.trace_context import get_current_trace_id
        trace_id = get_current_trace_id()
    except Exception:
        pass

    # ── normalise payload ──
    if isinstance(payload, CashflowEnvelope):
        logger.info(
            "integrate-all: envelope format received (monthly len=%d) trace_id=%s client_id=%s",
            len(payload.monthly), trace_id, client_id,
        )
        if not payload.monthly:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scenario cashflow cannot be empty",
            )
        scenario_cashflow: List[Dict[str, Any]] = [
            {
                "date": m.date,
                "inflow": m.income,
                "outflow": m.expenses,
                "net": m.net,
            }
            for m in payload.monthly
        ]
    else:
        # payload is List[ScenarioCashflowItem]
        logger.info(
            "integrate-all: list format received (len=%d) trace_id=%s client_id=%s",
            len(payload), trace_id, client_id,
        )
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scenario cashflow cannot be empty",
            )
        scenario_cashflow = [item.model_dump() for item in payload]

    # ── verify client exists ──
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found",
        )

    # ── validate required fields ──
    required_fields = ['date', 'inflow', 'outflow', 'net']
    for i, item in enumerate(scenario_cashflow):
        for field in required_fields:
            if field not in item:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing required field '{field}' in scenario cashflow item {i}",
                )

    try:
        # Convert date strings to date objects if needed
        for item in scenario_cashflow:
            if isinstance(item['date'], str):
                item['date'] = date.fromisoformat(item['date'])

        integrated_cashflow = integrate_all_incomes_with_scenario(
            db, client_id, scenario_cashflow, reference_date
        )

        return integrated_cashflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error integrating all income sources: {str(e)}",
        )
