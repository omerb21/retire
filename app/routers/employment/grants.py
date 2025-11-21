"""
Grants Management Router
Endpoints for managing employer grants
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.current_employer import EmploymentService, GrantService
from app.schemas.current_employer import (
    EmployerGrantCreate,
    GrantWithCalculation
)

router = APIRouter()


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
    try:
        # Get employer
        employment_service = EmploymentService(db)
        ce = employment_service.get_employer(client_id)
        
        # Add grant
        grant_service = GrantService(db)
        grant, calculation = grant_service.add_grant(ce, grant_data)
        
        # Return grant with calculation results
        return GrantWithCalculation(
            **grant.to_dict(),
            calculation=calculation
        )
        
    except ValueError as e:
        message = str(e)
        # Map known business errors to 404 as expected by tests
        not_found_messages = {
            "לקוח לא נמצא",
            "אין מעסיק נוכחי רשום ללקוח",
            "מעסיק נוכחי לא נמצא",
        }
        status_code = status.HTTP_404_NOT_FOUND if ("לא נמצא" in message or message in not_found_messages) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail={"error": message},
        )
