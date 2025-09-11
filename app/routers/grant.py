"""
Grant API router - Sprint 3
Endpoints for managing grants from past employers
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.client import Client
from app.models.grant import Grant
from app.schemas.grant import GrantCreate, GrantUpdate, GrantOut, GrantWithCalculation
from app.services.grant_service import GrantService

router = APIRouter()

@router.post(
    "/clients/{client_id}/grants",
    response_model=GrantOut,
    status_code=status.HTTP_201_CREATED
)
def create_grant(
    client_id: int,
    grant_data: GrantCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new grant for a client
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    try:
        # Create grant directly in database
        grant = Grant(
            client_id=client_id,
            employer_name=grant_data.employer_name,
            work_start_date=grant_data.work_start_date,
            work_end_date=grant_data.work_end_date,
            grant_amount=grant_data.grant_amount,
            grant_date=grant_data.grant_date
        )
        
        db.add(grant)
        db.commit()
        db.refresh(grant)
        
        return grant
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה ביצירת מענק: {str(e)}"}
        )

@router.get(
    "/clients/{client_id}/grants",
    response_model=List[GrantOut]
)
def get_client_grants(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all grants for a client
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get grants
    grants = db.query(Grant).filter(Grant.client_id == client_id).all()
    return grants

@router.get(
    "/clients/{client_id}/grants/{grant_id}",
    response_model=GrantOut
)
def get_grant(
    client_id: int,
    grant_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific grant
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get grant
    grant = db.query(Grant).filter(Grant.id == grant_id, Grant.client_id == client_id).first()
    if not grant:
        raise HTTPException(
            status_code=404,
            detail={"error": "מענק לא נמצא"}
        )
    
    return grant

@router.delete(
    "/clients/{client_id}/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_grant(
    client_id: int,
    grant_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a grant
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get grant
    grant = db.query(Grant).filter(Grant.id == grant_id, Grant.client_id == client_id).first()
    if not grant:
        raise HTTPException(
            status_code=404,
            detail={"error": "מענק לא נמצא"}
        )
    
    # Delete grant
    db.delete(grant)
    db.commit()
    
    return None
