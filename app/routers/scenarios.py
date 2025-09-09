"""
Scenarios router with CRUD operations for Scenario management
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.client import Client
from app.models.scenario import Scenario
from app.schemas import (
    ScenarioCreate, ScenarioUpdate, Scenario as ScenarioResponse,
    APIResponse
)
from app.services.calculations import generate_cashflow

router = APIRouter(
    prefix="/api/v1/clients",
    tags=["scenarios"],
    responses={404: {"description": "Not found"}},
)


@router.post("/{client_id}/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    scenario: ScenarioCreate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Create a new scenario for a client and run cashflow generation"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Parse scenario parameters
    try:
        scenario_params = json.loads(scenario.parameters) if scenario.parameters != "{}" else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON in parameters field"
        )
    
    # Generate cashflow using the calculation engine
    try:
        cashflow_result = generate_cashflow(client_id, scenario_params)
        cashflow_json = json.dumps(cashflow_result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cashflow: {str(e)}"
        )
    
    # Create scenario with generated cashflow
    scenario_data = scenario.model_dump()
    scenario_data["client_id"] = client_id
    scenario_data["cashflow_projection"] = cashflow_json
    
    # Create summary results from cashflow
    summary_results = {
        "total_months": len(cashflow_result.get("monthly", [])),
        "yearly_totals": cashflow_result.get("yearly_totals", {}),
        "status": "completed",
        "generated_at": cashflow_result.get("calculation_date")
    }
    scenario_data["summary_results"] = json.dumps(summary_results)
    
    db_scenario = Scenario(**scenario_data)
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    
    return db_scenario


@router.get("/{client_id}/scenarios", response_model=List[ScenarioResponse])
def get_client_scenarios(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Get all scenarios for a client"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    scenarios = db.query(Scenario).filter(Scenario.client_id == client_id).all()
    return scenarios


@router.get("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get specific scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    return db_scenario


@router.put("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario: ScenarioUpdate,
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Update scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    # Update only provided fields
    update_data = scenario.model_dump(exclude_unset=True)
    
    # If parameters are updated, regenerate cashflow
    if "parameters" in update_data:
        try:
            scenario_params = json.loads(update_data["parameters"]) if update_data["parameters"] != "{}" else {}
            cashflow_result = generate_cashflow(client_id, scenario_params)
            update_data["cashflow_projection"] = json.dumps(cashflow_result)
            
            # Update summary results
            summary_results = {
                "total_months": len(cashflow_result.get("monthly", [])),
                "yearly_totals": cashflow_result.get("yearly_totals", {}),
                "status": "completed",
                "generated_at": cashflow_result.get("calculation_date")
            }
            update_data["summary_results"] = json.dumps(summary_results)
        except (json.JSONDecodeError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to process parameters or generate cashflow: {str(e)}"
            )
    
    for field, value in update_data.items():
        setattr(db_scenario, field, value)
    
    db.commit()
    db.refresh(db_scenario)
    
    return db_scenario


@router.delete("/{client_id}/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Delete scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    db.delete(db_scenario)
    db.commit()


@router.get("/{client_id}/scenarios/{scenario_id}/cashflow")
def get_scenario_cashflow(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get cashflow data for a specific scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    if not db_scenario.cashflow_projection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cashflow data available for this scenario"
        )
    
    try:
        cashflow_data = json.loads(db_scenario.cashflow_projection)
        return cashflow_data
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid cashflow data format"
        )
