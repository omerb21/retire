"""
Main scenarios router - combines basic CRUD and retirement scenarios
"""
from typing import List
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from .schemas import ScenarioCreate, ScenarioUpdate, ScenarioResponse
from .crud import (
    create_scenario_with_cashflow,
    get_scenarios_by_client,
    get_scenario_by_id,
    update_scenario_by_id,
    delete_scenario_by_id,
    get_scenario_cashflow
)
from .retirement.router import router as retirement_router

# Create main router
router = APIRouter(
    prefix="/api/v1/clients",
    tags=["scenarios"],
    responses={404: {"description": "Not found"}},
)


# ===== Basic CRUD Endpoints =====

@router.post("/{client_id}/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    scenario: ScenarioCreate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Create a new scenario for a client and run cashflow generation"""
    return create_scenario_with_cashflow(db, client_id, scenario)


@router.get("/{client_id}/scenarios", response_model=List[ScenarioResponse])
def get_client_scenarios(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Get all scenarios for a client"""
    return get_scenarios_by_client(db, client_id)


@router.get("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get specific scenario"""
    return get_scenario_by_id(db, client_id, scenario_id)


@router.put("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario: ScenarioUpdate,
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Update scenario"""
    return update_scenario_by_id(db, client_id, scenario_id, scenario)


@router.delete("/{client_id}/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Delete scenario"""
    delete_scenario_by_id(db, client_id, scenario_id)


@router.get("/{client_id}/scenarios/{scenario_id}/cashflow")
def get_cashflow(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get cashflow data for a specific scenario"""
    return get_scenario_cashflow(db, client_id, scenario_id)


# ===== Include Retirement Router =====
# Include all retirement-specific endpoints
router.include_router(retirement_router)
