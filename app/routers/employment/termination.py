"""
Termination Processing Router
Endpoints for processing employee termination decisions
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.client import Client
from app.services.current_employer import EmploymentService, TerminationService
from app.schemas.current_employer import (
    TerminationDecisionCreate,
    TerminationDecisionOut
)

router = APIRouter()


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
