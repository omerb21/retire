"""
Employer Management Router
Endpoints for managing current employer CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.current_employer import EmploymentService
from app.schemas.current_employer import (
    CurrentEmployerCreate,
    CurrentEmployerOut
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
    try:
        service = EmploymentService(db)
        ce = service.create_or_update_employer(client_id, employer_data)
        return ce
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "לקוח לא נמצא" in str(e) else 400,
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
    try:
        service = EmploymentService(db)
        ce = service.get_employer(client_id)
        return CurrentEmployerOut.model_validate(ce)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
