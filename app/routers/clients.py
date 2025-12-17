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
from app.services.current_employer_service import CurrentEmployerService
from app.services.client_crud_service import ClientCrudService
from app.services.fixation_result_service import get_client_fixation_response
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
        return ClientCrudService.create_client(db=db, client=client)
    except ValueError as e:
        if str(e) == "duplicate_id_number":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this ID number already exists",
            )
        raise


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int = Path(..., description="Client ID"), db: Session = Depends(get_db)):
    """Get client by ID"""
    try:
        return ClientCrudService.get_client(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        raise


def _update_client_impl(client: ClientUpdate, client_id: int, db: Session) -> Client:
    """Internal helper to update a client instance"""
    try:
        return ClientCrudService.update_client(db=db, client_id=client_id, client=client)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        if str(e) == "duplicate_id_number":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this ID number already exists",
            )
        raise


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
    try:
        ClientCrudService.delete_client(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        raise


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
    items, total = ClientCrudService.list_clients(
        db=db,
        skip=skip,
        limit=limit,
        is_active=is_active,
        gender=gender,
        search=search,
        sort=sort,
    )

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
    db_employer = CurrentEmployerService.get_current_employer_by_id_for_client(
        db=db,
        client_id=client_id,
        employer_id=employer_id,
    )
    if not db_employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found",
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
    db_employer = CurrentEmployerService.update_current_employer_for_client(
        db=db,
        client_id=client_id,
        employer_id=employer_id,
        employer_data=employer,
    )
    if not db_employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found",
        )
    return db_employer


@router.delete("/{client_id}/current-employer/{employer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_employer(
    client_id: int = Path(..., description="Client ID"),
    employer_id: int = Path(..., description="Employer ID"),
    db: Session = Depends(get_db)
):
    """Delete current employer"""
    deleted = CurrentEmployerService.delete_current_employer_for_client(
        db=db,
        client_id=client_id,
        employer_id=employer_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current employer not found",
        )

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
    try:
        return get_client_fixation_response(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        if str(e) == "no_fixation_data":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No fixation data found for this client",
            )
        raise
