from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from typing import List

from app.database import get_db
from app.schemas.cashflow import (
    CashflowGenerateRequest,
    CashflowGenerateResponse,
)
from app.services.cashflow_service import generate_cashflow

router = APIRouter(
    prefix="/api/v1/scenarios/{scenario_id}/cashflow",
    tags=["cashflow"],
)


@router.post(
    "/generate",
    response_model=CashflowGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate monthly cashflow for a scenario",
    description="""
    Generate monthly cashflow data for a given scenario and client.
    
    This endpoint integrates additional incomes and capital assets with base scenario data
    to produce a comprehensive monthly cashflow projection.
    
    **Request Body Example:**
    ```json
    {
        "from": "2025-01",
        "to": "2025-12", 
        "frequency": "monthly"
    }
    ```
    
    **Response Example:**
    ```json
    [
        {
            "date": "2025-01-01",
            "inflow": 2513800.0,
            "outflow": 0.0,
            "additional_income_net": 2013800.0,
            "capital_return_net": 500000.0,
            "net": 5027600.0
        },
        {
            "date": "2025-02-01", 
            "inflow": 2513800.0,
            "outflow": 0.0,
            "additional_income_net": 2013800.0,
            "capital_return_net": 500000.0,
            "net": 5027600.0
        }
    ]
    ```
    """,
)
def generate_cashflow_endpoint(
    scenario_id: int,
    req: CashflowGenerateRequest,
    client_id: int = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
):
    try:
        data = generate_cashflow(
            db=db,
            client_id=client_id,
            scenario_id=scenario_id,
            start_ym=req.from_,
            end_ym=req.to,
            frequency=req.frequency,
        )
        return data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate cashflow: {e}")
