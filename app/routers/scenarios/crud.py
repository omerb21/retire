"""
CRUD operations for scenarios
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.services import scenario_crud_service
from .schemas import ScenarioCreate, ScenarioUpdate, ScenarioResponse


def get_client_or_404(db: Session, client_id: int) -> Client:
    """Get client by ID or raise 404"""
    return scenario_crud_service.get_client_or_404(db=db, client_id=client_id)


def create_scenario_with_cashflow(
    db: Session, client_id: int, scenario: ScenarioCreate
) -> ScenarioResponse:
    """Create a new scenario with cashflow generation"""
    return scenario_crud_service.create_scenario_with_cashflow(
        db=db,
        client_id=client_id,
        scenario=scenario,
    )


def get_scenarios_by_client(db: Session, client_id: int) -> List[ScenarioResponse]:
    """Get all scenarios for a client"""
    return scenario_crud_service.get_scenarios_by_client(db=db, client_id=client_id)


def get_scenario_by_id(
    db: Session, client_id: int, scenario_id: int
) -> ScenarioResponse:
    """Get specific scenario"""
    return scenario_crud_service.get_scenario_by_id(
        db=db,
        client_id=client_id,
        scenario_id=scenario_id,
    )


def update_scenario_by_id(
    db: Session, client_id: int, scenario_id: int, scenario: ScenarioUpdate
) -> ScenarioResponse:
    """Update scenario"""
    return scenario_crud_service.update_scenario_by_id(
        db=db,
        client_id=client_id,
        scenario_id=scenario_id,
        scenario=scenario,
    )


def delete_scenario_by_id(db: Session, client_id: int, scenario_id: int) -> None:
    """Delete scenario"""
    scenario_crud_service.delete_scenario_by_id(
        db=db,
        client_id=client_id,
        scenario_id=scenario_id,
    )


def get_scenario_cashflow(db: Session, client_id: int, scenario_id: int) -> dict:
    """Get cashflow data for a specific scenario"""
    return scenario_crud_service.get_scenario_cashflow(
        db=db,
        client_id=client_id,
        scenario_id=scenario_id,
    )
