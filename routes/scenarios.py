"""
FastAPI routes for Scenario management and execution
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from db.session import get_db
from models.scenario import Scenario
from models.scenario_cashflow import ScenarioCashflow
from models.client import Client
from services.scenario_engine import run_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

@router.post("/")
def create_scenario(
    client_id: int,
    name: str,
    parameters: dict = None,
    db: Session = Depends(get_db)
):
    """Create a new scenario for a client"""
    
    # Verify client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Create scenario
    scenario = Scenario(
        client_id=client_id,
        name=name,
        parameters_json=json.dumps(parameters or {}),
        status="draft"
    )
    
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    
    return {
        "id": scenario.id,
        "client_id": scenario.client_id,
        "name": scenario.name,
        "status": scenario.status,
        "message": "Scenario created successfully"
    }

@router.get("/{scenario_id}")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Get scenario details"""
    
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    return {
        "id": scenario.id,
        "client_id": scenario.client_id,
        "name": scenario.name,
        "status": scenario.status,
        "parameters": json.loads(scenario.parameters_json) if scenario.parameters_json else {},
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at
    }

@router.put("/{scenario_id}")
def update_scenario(
    scenario_id: int,
    name: Optional[str] = None,
    parameters: Optional[dict] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update scenario details"""
    
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Update fields if provided
    if name is not None:
        scenario.name = name
    if parameters is not None:
        scenario.parameters_json = json.dumps(parameters)
    if status is not None:
        scenario.status = status
    
    db.commit()
    db.refresh(scenario)
    
    return {
        "id": scenario.id,
        "name": scenario.name,
        "status": scenario.status,
        "message": "Scenario updated successfully"
    }

@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Delete a scenario and its cashflow data"""
    
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    db.delete(scenario)
    db.commit()
    
    return {"message": "Scenario deleted successfully"}

@router.post("/{scenario_id}/run")
def run_scenario_calculation(scenario_id: int, db: Session = Depends(get_db)):
    """Execute scenario calculation and generate cashflow"""
    
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    try:
        # Run the scenario calculation
        cashflow = run_scenario(db, scenario.client_id, scenario_id)
        
        return {
            "message": "Scenario calculation completed successfully",
            "scenario_id": scenario_id,
            "cashflow_years": len(cashflow),
            "total_net_income": sum(entry["net_income"] for entry in cashflow),
            "cashflow": cashflow
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario calculation failed: {str(e)}")

@router.get("/{scenario_id}/cashflow")
def get_scenario_cashflow(
    scenario_id: int,
    year_from: Optional[int] = Query(None, description="Start year filter"),
    year_to: Optional[int] = Query(None, description="End year filter"),
    db: Session = Depends(get_db)
):
    """Get cashflow data for a scenario"""
    
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Build query
    query = db.query(ScenarioCashflow).filter(ScenarioCashflow.scenario_id == scenario_id)
    
    if year_from:
        query = query.filter(ScenarioCashflow.year >= year_from)
    if year_to:
        query = query.filter(ScenarioCashflow.year <= year_to)
    
    cashflow_records = query.order_by(ScenarioCashflow.year).all()
    
    cashflow_data = [
        {
            "year": record.year,
            "gross_income": record.gross_income,
            "pension_income": record.pension_income,
            "grant_income": record.grant_income,
            "other_income": record.other_income,
            "tax": record.tax,
            "net_income": record.net_income
        }
        for record in cashflow_records
    ]
    
    # Calculate summary statistics
    total_gross = sum(entry["gross_income"] for entry in cashflow_data)
    total_tax = sum(entry["tax"] for entry in cashflow_data)
    total_net = sum(entry["net_income"] for entry in cashflow_data)
    
    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario.name,
        "scenario_status": scenario.status,
        "cashflow": cashflow_data,
        "summary": {
            "years": len(cashflow_data),
            "total_gross_income": total_gross,
            "total_tax": total_tax,
            "total_net_income": total_net,
            "average_annual_net": total_net / len(cashflow_data) if cashflow_data else 0
        }
    }

@router.get("/client/{client_id}")
def list_client_scenarios(
    client_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all scenarios for a specific client"""
    
    # Verify client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Build query
    query = db.query(Scenario).filter(Scenario.client_id == client_id)
    if status:
        query = query.filter(Scenario.status == status)
    
    scenarios = query.order_by(Scenario.created_at.desc()).all()
    
    scenario_list = [
        {
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "parameters": json.loads(s.parameters_json) if s.parameters_json else {}
        }
        for s in scenarios
    ]
    
    return {
        "client_id": client_id,
        "client_name": client.full_name,
        "scenarios": scenario_list,
        "total_scenarios": len(scenario_list)
    }
