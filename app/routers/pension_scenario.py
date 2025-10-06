from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.client import Client
from app.schemas.scenario import ScenarioIn, ScenarioOut
from app.calculation.engine import CalculationEngine
from app.calculation.pension_integration import (
    generate_combined_pension_cashflow,
    integrate_pension_funds_with_scenario
)
from app.providers.tax_params import TaxParamsProvider
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["pension-scenarios"])

class PensionScenarioRequest(BaseModel):
    scenario: ScenarioIn
    include_pension_funds: bool = True
    reference_date: Optional[date] = None

class PensionCashflowResponse(BaseModel):
    date: date
    total_amount: float
    funds: List[dict]

@router.post("/clients/{client_id}/pension-cashflow", response_model=List[PensionCashflowResponse])
def get_pension_cashflow(
    client_id: int,
    months: int = 12,
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get pension cashflow for a client"""
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
    
    # Generate pension cashflow
    cashflow = generate_combined_pension_cashflow(db, client_id, months, reference_date)
    if not cashflow:
        return []
    
    return cashflow

@router.post("/clients/{client_id}/pension-scenario", response_model=dict)
def calculate_pension_scenario(
    client_id: int,
    request: PensionScenarioRequest,
    db: Session = Depends(get_db)
):
    """Calculate scenario with pension funds integration"""
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
    
    # Initialize calculation engine
    tax_provider = TaxParamsProvider()
    engine = CalculationEngine(db, tax_provider)
    
    # Run basic scenario calculation
    try:
        scenario_result = engine.run(client_id, request.scenario)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    
    # Convert to dict for modification
    result_dict = scenario_result.model_dump()
    
    # Integrate pension funds if requested
    if request.include_pension_funds:
        # Get cashflow from scenario
        scenario_cashflow = result_dict.get("cashflow", [])
        
        # Integrate pension funds
        integrated_cashflow = integrate_pension_funds_with_scenario(
            db, 
            client_id, 
            scenario_cashflow,
            request.reference_date
        )
        
        # Update result with integrated cashflow
        result_dict["cashflow"] = integrated_cashflow
        
        # Add pension summary
        if integrated_cashflow:
            first_month = integrated_cashflow[0]
            result_dict["pension_monthly"] = first_month.get("pension_income", 0.0)
            result_dict["has_pension_funds"] = True
    
    return result_dict
