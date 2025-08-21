"""API router for Additional Income management."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.additional_income import AdditionalIncome
from app.schemas.additional_income import (
    AdditionalIncomeCreate,
    AdditionalIncomeUpdate,
    AdditionalIncomeResponse
)

router = APIRouter(prefix="/clients/{client_id}/additional-incomes", tags=["additional-incomes"])


@router.post("/", response_model=AdditionalIncomeResponse, status_code=status.HTTP_201_CREATED)
def create_additional_income(
    client_id: int,
    income_data: AdditionalIncomeCreate,
    db: Session = Depends(get_db)
):
    """Create a new additional income source for a client."""
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    # Create additional income
    db_income = AdditionalIncome(
        client_id=client_id,
        **income_data.dict()
    )
    
    db.add(db_income)
    db.commit()
    db.refresh(db_income)
    
    return db_income


@router.get("/", response_model=List[AdditionalIncomeResponse])
def get_additional_incomes(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Get all additional income sources for a client."""
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    incomes = db.query(AdditionalIncome).filter(
        AdditionalIncome.client_id == client_id
    ).all()
    
    return incomes


@router.get("/{income_id}", response_model=AdditionalIncomeResponse)
def get_additional_income(
    client_id: int,
    income_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific additional income source."""
    income = db.query(AdditionalIncome).filter(
        AdditionalIncome.id == income_id,
        AdditionalIncome.client_id == client_id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Additional income with id {income_id} not found for client {client_id}"
        )
    
    return income


@router.put("/{income_id}", response_model=AdditionalIncomeResponse)
def update_additional_income(
    client_id: int,
    income_id: int,
    income_data: AdditionalIncomeUpdate,
    db: Session = Depends(get_db)
):
    """Update an additional income source."""
    income = db.query(AdditionalIncome).filter(
        AdditionalIncome.id == income_id,
        AdditionalIncome.client_id == client_id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Additional income with id {income_id} not found for client {client_id}"
        )
    
    # Update fields
    update_data = income_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(income, field, value)
    
    db.commit()
    db.refresh(income)
    
    return income


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_additional_income(
    client_id: int,
    income_id: int,
    db: Session = Depends(get_db)
):
    """Delete an additional income source."""
    income = db.query(AdditionalIncome).filter(
        AdditionalIncome.id == income_id,
        AdditionalIncome.client_id == client_id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Additional income with id {income_id} not found for client {client_id}"
        )
    
    db.delete(income)
    db.commit()
    
    return None
