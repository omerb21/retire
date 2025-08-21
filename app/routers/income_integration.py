"""API router for income and asset integration with scenario cashflow."""

from datetime import date
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.calculation.income_integration import (
    integrate_additional_incomes_with_scenario,
    integrate_capital_assets_with_scenario,
    integrate_all_incomes_with_scenario
)

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


@router.post("/integrate-all", response_model=List[Dict[str, Any]])
def integrate_all_with_cashflow(
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = Query(None, description="Reference date for calculations"),
    db: Session = Depends(get_db)
):
    """
    Integrate both additional incomes and capital assets with scenario cashflow.
    
    Args:
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with all income sources integrated
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
        
        integrated_cashflow = integrate_all_incomes_with_scenario(
            db, client_id, scenario_cashflow, reference_date
        )
        
        return integrated_cashflow
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error integrating all income sources: {str(e)}"
        )
