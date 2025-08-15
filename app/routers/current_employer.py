"""
Current Employer API router - Sprint 3
Endpoints for managing current employer and grants
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date
from app.database import get_db
from app.models import Client, CurrentEmployer
from app.services.current_employer_service import CurrentEmployerService
from app.schemas.current_employer import (
    CurrentEmployerCreate, CurrentEmployerUpdate, CurrentEmployerOut,
    EmployerGrantCreate, GrantWithCalculation
)

router = APIRouter()

@router.post(
    "/clients/{client_id}/current-employer",
    response_model=CurrentEmployerOut,
    status_code=status.HTTP_201_CREATED
)
def create_or_update_current_employer(
    client_id: int,
    employer_data: CurrentEmployerCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update current employer for a client
    Returns 201 for new creation, 200 for update
    """
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Check if current employer already exists using direct query - get latest
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    
    if ce:
        # Update existing employer
        data = employer_data.model_dump(exclude_none=True)  # Important! Don't overwrite with None
        for k, v in data.items():
            setattr(ce, k, v)
        ce.last_update = date.today()  # Always update by server
        
        db.add(ce)
        db.commit()
        db.refresh(ce)
        return ce
    else:
        # Create new employer
        try:
            # Could try to derive data from Employment "current" here if needed
            
            # Create new from payload
            ce = CurrentEmployer(
                client_id=client_id,
                **employer_data.model_dump(exclude_none=True)
            )
            ce.last_update = date.today()
            
            db.add(ce)
            db.commit()
            db.refresh(ce)
            return ce
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": str(e)}
            )

@router.get(
    "/clients/{client_id}/current-employer",
    response_model=CurrentEmployerOut
)
def get_current_employer(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current employer for a client
    Returns 404 if client not found or no current employer exists
    """
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get current employer using direct query - get latest
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    
    if not ce:
        # Could try to derive from Employment "current" here
        # For now, just return 404
        raise HTTPException(
            status_code=404,
            detail={"error": "אין מעסיק נוכחי רשום ללקוח"}
        )
    
    return ce

@router.post(
    "/clients/{client_id}/current-employer/grants",
    response_model=GrantWithCalculation,
    status_code=status.HTTP_201_CREATED
)
def add_grant_to_current_employer(
    client_id: int,
    grant_data: EmployerGrantCreate,
    db: Session = Depends(get_db)
):
    """
    Add a grant to current employer and return calculation results
    Includes grant_exempt, grant_taxable, tax_due in response
    """
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get current employer using direct query - get latest
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    if not ce:
        raise HTTPException(
            status_code=404,
            detail={"error": "אין מעסיק נוכחי רשום ללקוח"}
        )
    
    try:
        # Add grant and calculate results
        grant, calculation = CurrentEmployerService.add_grant_to_employer(
            db, ce.id, grant_data
        )
        
        # Return grant with calculation results
        return GrantWithCalculation(
            **grant.to_dict(),
            calculation=calculation
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e)}
        )
