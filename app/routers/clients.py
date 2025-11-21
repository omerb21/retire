"""
Clients router with CRUD operations for Client and CurrentEmployer
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.database import get_db
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.services.retirement.utils.pension_utils import compute_pension_start_date_from_funds
from app.services.client_service import normalize_id_number
from app.services.current_employer import EmploymentService as CurrentEmployerEmploymentService
# ייבוא סכמות הלקוח
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientList

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
        # Normalize ID number from either id_number or id_number_raw
        normalized_id = client.id_number
        if not normalized_id and client.id_number_raw:
            normalized_id = normalize_id_number(client.id_number_raw)

        # Check if client with this ID number already exists
        existing_client = db.query(Client).filter(Client.id_number == normalized_id).first()
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this ID number already exists"
            )
        
        # Create new client
        client_data = client.model_dump()
        if normalized_id:
            client_data["id_number"] = normalized_id
        db_client = Client(**client_data)
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
    
    # אם לא הוגדר תאריך תחילת קצבה ללקוח, נחשב אותו מקצבאות הפנסיה ונשמור פעם אחת
    if not db_client.pension_start_date:
        effective_pension_start_date = compute_pension_start_date_from_funds(db, db_client)
        if effective_pension_start_date:
            db_client.pension_start_date = effective_pension_start_date
            db.add(db_client)
            db.commit()
            db.refresh(db_client)

    return db_client


def _update_client_impl(client: ClientUpdate, client_id: int, db: Session) -> Client:
    """Internal helper to update a client instance"""
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


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client: ClientUpdate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Update client by ID using PUT"""
    return _update_client_impl(client, client_id, db)


@router.patch("/{client_id}", response_model=ClientResponse)
def patch_client(
    client: ClientUpdate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Partially update client by ID using PATCH"""
    return _update_client_impl(client, client_id, db)


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


@router.get("", response_model=ClientList)
def list_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    search: Optional[str] = Query(None, description="Search by name or ID"),
    sort: Optional[str] = Query(None, description="Sort field, e.g. 'full_name'"),
    db: Session = Depends(get_db),
):
    """List clients with pagination, filtering, sorting, and search"""
    query = db.query(Client)

    if is_active is not None:
        query = query.filter(Client.is_active == is_active)
    if gender is not None:
        query = query.filter(Client.gender == gender)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Client.full_name.ilike(pattern),
                Client.id_number.ilike(pattern),
            )
        )

    total = query.count()

    if sort == "full_name":
        query = query.order_by(Client.full_name.asc())

    items = query.offset(skip).limit(limit).all()

    page_size = limit
    page = (skip // page_size) + 1 if page_size else 1

    return ClientList(items=items, total=total, page=page, page_size=page_size)


"""Current Employer CRUD operations bound to /api/v1/clients/{client_id}/current-employer"""


@router.post("/{client_id}/current-employer", response_model=CurrentEmployerOut, status_code=status.HTTP_201_CREATED)
def create_current_employer(
    employer: CurrentEmployerCreate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db),
):
    """Create or update current employer for a client.

    Uses the Sprint 3 EmploymentService to either create a new CurrentEmployer
    or update the latest one for this client. On business errors, returns
    structured Hebrew error messages as expected by the tests.
    """
    service = CurrentEmployerEmploymentService(db)
    try:
        current_employer = service.create_or_update_employer(client_id=client_id, employer_data=employer)
        return current_employer
    except ValueError as e:
        message = str(e)
        if message == "לקוח לא נמצא":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": message},
            )
        # For any other business error, return 400 with the message
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": message},
        )


@router.get("/{client_id}/current-employer", response_model=CurrentEmployerOut)
def get_current_employer_for_client(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db),
):
    """Get the current employer for a client.

    Returns the most recently updated CurrentEmployer record for the client.
    If the client does not exist or has no current employer, returns 404 with
    a structured Hebrew error message as expected by the tests.
    """
    service = CurrentEmployerEmploymentService(db)
    try:
        current_employer = service.get_employer(client_id)
        return current_employer
    except ValueError as e:
        message = str(e)
        if message in ("לקוח לא נמצא", "אין מעסיק נוכחי רשום ללקוח"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": message},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": message},
        )


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
