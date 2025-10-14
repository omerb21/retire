"""
Pension Router - handles CRUD operations for pensions (קצבאות)
Different from pension_fund which handles pension fund portfolios
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.pension import Pension

router = APIRouter(prefix="/clients", tags=["pensions"])

@router.get("/{client_id}/pensions", response_model=List[dict])
def get_client_pensions(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Get all pensions for a client"""
    pensions = db.query(Pension).filter(Pension.client_id == client_id).all()
    return [p.to_dict() for p in pensions]

@router.get("/{client_id}/pensions/{pension_id}", response_model=dict)
def get_pension(
    client_id: int,
    pension_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific pension"""
    pension = db.query(Pension).filter(
        Pension.id == pension_id,
        Pension.client_id == client_id
    ).first()
    
    if not pension:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pension {pension_id} not found for client {client_id}"
        )
    
    return pension.to_dict()

@router.delete("/{client_id}/pensions/{pension_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pension(
    client_id: int,
    pension_id: int,
    db: Session = Depends(get_db)
):
    """Delete a pension"""
    pension = db.query(Pension).filter(
        Pension.id == pension_id,
        Pension.client_id == client_id
    ).first()
    
    if not pension:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pension {pension_id} not found for client {client_id}"
        )
    
    db.delete(pension)
    db.commit()
    return None
