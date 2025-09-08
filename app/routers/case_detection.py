"""
Case detection router for determining client workflow path
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.schemas.case import CaseDetectionResponse, CaseDetectionResult, CaseDetectResponse, ClientCase
from app.utils.contract_adapter import CaseDetectionAdapter

router = APIRouter(
    prefix="/clients",
    tags=["case-detection"],
)


@router.get(
    "/{client_id}/case/detect",
    response_model=CaseDetectionResponse,
    summary="Detect client case (workflow type)",
    response_description="Client case detection result with reasoning"
)
def detect_client_case_get(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db),
):
    """
    Detect the appropriate case (workflow type) for a client based on their data.
    
    The system evaluates client data according to the following rules:
    - Case 1: Client with no current employer
    - Case 2: Client with no current employer but has business income (self-employed)
    - Case 3: Client is past retirement age
    - Case 4: Client has current employer with no planned leave
    - Case 5: Client has current employer with planned leave/termination (default workflow)
    
    The API returns the case ID, name, and reasoning behind the classification.
    
    Example response:
    ```json
    {
      "result": {
        "client_id": 1,
        "case_id": 5,
        "case_name": "REGULAR_WITH_LEAVE",
        "reasons": ["has_current_employer", "planned_leave_detected_or_default"],
        "detected_at": "2025-09-03T13:25:00Z"
      }
    }
    ```
    """
    try:
        result = detect_case(db=db, client_id=client_id)
        return CaseDetectionResponse(result=result)
    except ValueError as e:
        # Client not found or missing required data
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Client with ID {client_id} not found"
            )
        else:
            # Other validation errors (like missing birth date)
            raise HTTPException(
                status_code=422,
                detail=str(e)
            )
    except Exception as e:
        # Unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Error detecting client case: {str(e)}"
        )


@router.post(
    "/{client_id}/case/detect",
    response_model=CaseDetectResponse,
    summary="Detect case via POST (Sprint 11 compatibility)"
)
def detect_case_post(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
) -> CaseDetectResponse:
    """
    POST version of case detection for Sprint 11 verification compatibility.
    Returns simple case detection result.
    """
    try:
        result = CaseDetectionAdapter.detect_case_for_api(db, client_id)
        return CaseDetectResponse(case=result["case"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Case detection failed: {str(e)}")
