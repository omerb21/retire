"""
Clients router with CRUD operations for Client and CurrentEmployer
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
# ייבוא סכמות הלקוח
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse

# ייבוא סכמות המעסיק הנוכחי
try:
    from app.schemas.current_employer import CurrentEmployerCreate, CurrentEmployerUpdate, CurrentEmployerOut
except ImportError:
    # יצירת סכמות זמניות אם הקובץ לא קיים
    from pydantic import BaseModel
    from typing import Optional
    from datetime import date
    
    class CurrentEmployerBase(BaseModel):
        employer_name: str
        start_date: date
        last_salary: Optional[float] = None
        severance_accrued: Optional[float] = None
    
    class CurrentEmployerCreate(CurrentEmployerBase):
        pass
    
    class CurrentEmployerUpdate(CurrentEmployerBase):
        employer_name: Optional[str] = None
        start_date: Optional[date] = None
        last_salary: Optional[float] = None
        severance_accrued: Optional[float] = None
    
    class CurrentEmployerOut(CurrentEmployerBase):
        id: int
        client_id: int
        created_at: date
        updated_at: date
        
        class Config:
            from_attributes = True

# ייבוא סכמת תגובת API
from app.schemas import APIResponse

router = APIRouter(
    prefix="/api/v1/clients",
    tags=["clients"],
    responses={404: {"description": "Not found"}},
)


# Client CRUD operations
@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client"""
    try:
        # Check if client with this ID number already exists
        existing_client = db.query(Client).filter(Client.id_number == client.id_number).first()
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this ID number already exists"
            )
        
        # Create new client
        db_client = Client(**client.model_dump())
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        
        return db_client
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client with this ID number already exists"
        )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int = Path(..., description="Client ID"), db: Session = Depends(get_db)):
    """Get client by ID"""
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return db_client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client: ClientUpdate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Update client by ID"""
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Update only provided fields
    update_data = client.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_client, field, value)
    
    try:
        db.commit()
        db.refresh(db_client)
        return db_client
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client with this ID number already exists"
        )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: int = Path(..., description="Client ID"), db: Session = Depends(get_db)):
    """Delete client by ID"""
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    db.delete(db_client)
    db.commit()


@router.get("", response_model=List[ClientResponse])
def list_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """List clients with pagination"""
    clients = db.query(Client).offset(skip).limit(limit).all()
    return clients


# Current Employer CRUD operations
@router.post("/{client_id}/current-employer", response_model=CurrentEmployerOut, status_code=status.HTTP_201_CREATED)
def create_current_employer(
    employer: CurrentEmployerCreate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Create current employer for a client"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Create current employer
    employer_data = employer.model_dump()
    employer_data["client_id"] = client_id
    db_employer = CurrentEmployer(**employer_data)
    
    db.add(db_employer)
    db.commit()
    db.refresh(db_employer)
    
    return db_employer


@router.get("/{client_id}/current-employer", response_model=List[CurrentEmployerOut])
def get_current_employers(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Get all current employers for a client"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    employers = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).all()
    return employers


@router.get("/{client_id}/current-employer/{employer_id}", response_model=CurrentEmployerOut)
def get_current_employer(
    client_id: int = Path(..., description="Client ID"),
    employer_id: int = Path(..., description="Employer ID"),
    db: Session = Depends(get_db)
):
    """Get specific current employer"""
    db_employer = db.query(CurrentEmployer).filter(
        CurrentEmployer.id == employer_id,
        CurrentEmployer.client_id == client_id
    ).first()
    
    if not db_employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found"
        )
    
    return db_employer


@router.put("/{client_id}/current-employer/{employer_id}", response_model=CurrentEmployerOut)
def update_current_employer(
    employer: CurrentEmployerUpdate,
    client_id: int = Path(..., description="Client ID"),
    employer_id: int = Path(..., description="Employer ID"),
    db: Session = Depends(get_db)
):
    """Update current employer"""
    db_employer = db.query(CurrentEmployer).filter(
        CurrentEmployer.id == employer_id,
        CurrentEmployer.client_id == client_id
    ).first()
    
    if not db_employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found"
        )
    
    # Update only provided fields
    update_data = employer.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_employer, field, value)
    
    db.commit()
    db.refresh(db_employer)
    
    return db_employer


@router.delete("/{client_id}/current-employer/{employer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_employer(
    client_id: int = Path(..., description="Client ID"),
    employer_id: int = Path(..., description="Employer ID"),
    db: Session = Depends(get_db)
):
    """Delete current employer"""
    db_employer = db.query(CurrentEmployer).filter(
        CurrentEmployer.id == employer_id,
        CurrentEmployer.client_id == client_id
    ).first()
    
    if not db_employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found"
        )
    
    db.delete(db_employer)
    db.commit()

# ==========================================
# FIXATION ENDPOINTS
# ==========================================

@router.get("/{client_id}/fixation", tags=["fixation"])
async def get_client_fixation(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """
    Get fixation of rights data for a client
    Returns the most recent fixation calculation results
    """
    from app.models.fixation_result import FixationResult
    from sqlalchemy import desc
    
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Get the most recent fixation result
    fixation = db.query(FixationResult).filter(
        FixationResult.client_id == client_id
    ).order_by(desc(FixationResult.created_at)).first()
    
    if not fixation or not fixation.raw_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No fixation data found for this client"
        )
    
    # Extract data from raw_result
    raw_result = fixation.raw_result
    
    # Build response in the format expected by SimpleReports
    response = {
        "id": fixation.id,
        "client_id": client_id,
        "created_at": fixation.created_at.isoformat() if fixation.created_at else None,
        "eligibility_year": raw_result.get("eligibility_year"),
        "exemption_summary": {
            "exemption_percentage": raw_result.get("exemption_summary", {}).get("exemption_percentage", 0),
            "general_exemption_percentage": raw_result.get("exemption_summary", {}).get("general_exemption_percentage", 0),
            "remaining_exempt_capital": raw_result.get("exemption_summary", {}).get("remaining_exempt_capital", 0),
            "remaining_monthly_exemption": raw_result.get("exemption_summary", {}).get("remaining_monthly_exemption", 0),
            "exempt_capital_initial": raw_result.get("exemption_summary", {}).get("exempt_capital_initial", 0),
            "eligibility_year": raw_result.get("exemption_summary", {}).get("eligibility_year", 0),
            "total_impact": raw_result.get("exemption_summary", {}).get("total_impact", 0)
        },
        "grants": raw_result.get("grants", []),
        "calculation_details": raw_result.get("calculation_details", {})
    }
    
    return response
