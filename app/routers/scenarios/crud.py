"""
CRUD operations for scenarios
"""
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.client import Client
from app.models.scenario import Scenario
from app.services.calculations import generate_cashflow
from .schemas import ScenarioCreate, ScenarioUpdate, ScenarioResponse


def get_client_or_404(db: Session, client_id: int) -> Client:
    """Get client by ID or raise 404"""
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return db_client


def create_scenario_with_cashflow(
    db: Session,
    client_id: int,
    scenario: ScenarioCreate
) -> ScenarioResponse:
    """Create a new scenario with cashflow generation"""
    # Check if client exists
    get_client_or_404(db, client_id)
    
    # Generate cashflow using the calculation engine
    try:
        cashflow_result = generate_cashflow(client_id, {})
        cashflow_json = json.dumps(cashflow_result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cashflow: {str(e)}"
        )
    
    # Create scenario with generated cashflow - map frontend fields to DB fields
    db_scenario = Scenario(
        client_id=client_id,
        scenario_name=scenario.name,
        parameters='{}',  # Default empty parameters
        cashflow_projection=cashflow_json
    )
    
    # Create summary results from cashflow
    summary_results = {
        "total_months": len(cashflow_result.get("monthly", [])),
        "yearly_totals": cashflow_result.get("yearly_totals", {}),
        "status": "completed",
        "generated_at": cashflow_result.get("calculation_date")
    }
    db_scenario.summary_results = json.dumps(summary_results)
    
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    
    return ScenarioResponse.from_db_scenario(db_scenario)


def get_scenarios_by_client(db: Session, client_id: int) -> List[ScenarioResponse]:
    """Get all scenarios for a client"""
    # Check if client exists
    get_client_or_404(db, client_id)
    
    scenarios = db.query(Scenario).filter(Scenario.client_id == client_id).all()
    return [ScenarioResponse.from_db_scenario(s) for s in scenarios]


def get_scenario_by_id(db: Session, client_id: int, scenario_id: int) -> ScenarioResponse:
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
    
    return ScenarioResponse.from_db_scenario(db_scenario)


def update_scenario_by_id(
    db: Session,
    client_id: int,
    scenario_id: int,
    scenario: ScenarioUpdate
) -> ScenarioResponse:
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


def delete_scenario_by_id(db: Session, client_id: int, scenario_id: int) -> None:
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


def get_scenario_cashflow(db: Session, client_id: int, scenario_id: int) -> dict:
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
