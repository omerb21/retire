"""
Severance Calculation Router
Endpoints for calculating severance payments
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.services.current_employer import TerminationService
from app.schemas.current_employer import (
    SeveranceCalculationRequest,
    SeveranceCalculationResponse
)

router = APIRouter()


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

        def parse_date(value: str | None):
            if not value:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"time data '{value}' does not match supported date formats")
        
        # Convert dates
        start_date = parse_date(request_data.start_date)
        end_date = parse_date(request_data.end_date) if request_data.end_date else date.today()
        
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
