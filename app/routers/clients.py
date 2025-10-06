"""
Clients router with CRUD operations for Client and CurrentEmployer
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
# ייבוא סכמות הלקוח
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse

# ייבוא סכמות המעסיק הנוכחי
try:
    from app.schemas.current_employer import CurrentEmployerCreate, CurrentEmployerUpdate, CurrentEmployerResponse
except ImportError:
    # יצירת סכמות זמניות אם הקובץ לא קיים
    from pydantic import BaseModel
    from typing import Optional
    from datetime import date
    
    class CurrentEmployerBase(BaseModel):
        employer_name: str
        start_date: date
        monthly_salary: float
        position: Optional[str] = None
    
    class CurrentEmployerCreate(CurrentEmployerBase):
        pass
    
    class CurrentEmployerUpdate(CurrentEmployerBase):
        employer_name: Optional[str] = None
        start_date: Optional[date] = None
        monthly_salary: Optional[float] = None
    
    class CurrentEmployerResponse(CurrentEmployerBase):
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
@router.post("/{client_id}/current-employer", response_model=CurrentEmployerResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/{client_id}/current-employer", response_model=List[CurrentEmployerResponse])
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


@router.get("/{client_id}/current-employer/{employer_id}", response_model=CurrentEmployerResponse)
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


@router.put("/{client_id}/current-employer/{employer_id}", response_model=CurrentEmployerResponse)
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
