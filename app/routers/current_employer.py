"""
Current Employer API router - Sprint 3 (Refactored)
Endpoints for managing current employer and grants

מודול מפוצל - משתמש בשירותים מודולריים
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.models.client import Client
from app.services.current_employer import (
    EmploymentService,
    GrantService,
    TerminationService
)
from app.schemas.current_employer import (
    CurrentEmployerCreate, CurrentEmployerOut,
    EmployerGrantCreate, GrantWithCalculation,
    TerminationDecisionCreate, TerminationDecisionOut,
    SeveranceCalculationRequest, SeveranceCalculationResponse
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
        raise HTTPException(
            status_code=404 if "לא נמצא" in str(e) else 400,
            detail={"error": str(e)}
        )


@router.post(
    "/clients/{client_id}/current-employer/termination",
    response_model=TerminationDecisionOut,
    status_code=status.HTTP_201_CREATED
)
def process_termination_decision(
    client_id: int,
    decision: TerminationDecisionCreate,
    db: Session = Depends(get_db)
):
    """
    Process employee termination decision and create appropriate entities:
    - Grant for exempt redemption with exemption usage
    - Pension for annuity choice
    - Capital Asset for tax spread choice
    
    Returns IDs of created entities
    """
    try:
        # Get client and employer
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError("לקוח לא נמצא")
        
        employment_service = EmploymentService(db)
        ce = employment_service.get_employer(client_id)
        
        # Process termination using service
        termination_service = TerminationService(db)
        result = termination_service.process_termination(client, ce, decision)
        
        # Return result with created IDs
        return TerminationDecisionOut(
            **decision.model_dump(),
            **result
        )
        
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=404 if "לא נמצא" in str(e) else 400,
            detail={"error": str(e)}
        )
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה בעיבוד החלטות עזיבה: {str(e)}"}
        )


@router.post(
    "/current-employer/calculate-severance",
    response_model=SeveranceCalculationResponse,
    status_code=status.HTTP_200_OK
)
def calculate_severance(
    request_data: SeveranceCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate severance payment based on employment details
    """
    try:
        from datetime import datetime
        
        # Convert dates
        start_date = datetime.strptime(request_data.start_date, '%Y-%m-%d').date() if request_data.start_date else None
        end_date = datetime.strptime(request_data.end_date, '%Y-%m-%d').date() if request_data.end_date else date.today()
        
        if not start_date:
            raise ValueError("חסר תאריך התחלת עבודה")
        
        # Use termination service for calculation
        termination_service = TerminationService(db)
        result = termination_service.calculate_severance(
            start_date=start_date,
            end_date=end_date,
            last_salary=request_data.last_salary,
            continuity_years=request_data.continuity_years or 0.0
        )
        
        return SeveranceCalculationResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": f"שגיאה בחישוב פיצויים: {str(e)}"}
        )


@router.delete(
    "/clients/{client_id}/delete-termination",
    status_code=status.HTTP_200_OK
)
def delete_termination_decision(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete all entities created by termination decision:
    - Grants
    - Pension Funds 
    - Capital Assets
    
    Also restores severance balance in pension portfolio (client-side)
    Returns the severance amount that should be restored
    """
    try:
        # Get client and employer
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError("לקוח לא נמצא")
        
        employment_service = EmploymentService(db)
        ce = employment_service.get_employer(client_id)
        
        # Delete termination using service
        termination_service = TerminationService(db)
        result = termination_service.delete_termination(client, ce)
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": str(e)}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה במחיקת החלטות עזיבה: {str(e)}"}
        )
