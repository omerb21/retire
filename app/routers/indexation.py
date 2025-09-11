"""
API endpoints for advanced indexation calculations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import date
from app.services.indexation_service import IndexationService

router = APIRouter()

class GrantCalculationRequest(BaseModel):
    grant_amount: float
    work_start_date: str
    work_end_date: str
    eligibility_date: Optional[str] = None

class GrantCalculationResponse(BaseModel):
    nominal_amount: float
    indexed_full: Optional[float] = None
    ratio: float
    indexed_amount: float
    impact_on_exemption: float
    calculation_details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@router.post("/calculate-exact", response_model=GrantCalculationResponse)
async def calculate_exact_grant_value(request: GrantCalculationRequest):
    """
    חישוב מדויק של ערך מענק כולל הצמדה ויחסים
    """
    try:
        grant_data = {
            'grant_amount': request.grant_amount,
            'work_start_date': request.work_start_date,
            'work_end_date': request.work_end_date
        }
        
        result = IndexationService.calculate_exact_grant_value(
            grant_data=grant_data,
            eligibility_date=request.eligibility_date
        )
        
        return GrantCalculationResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב הצמדה: {str(e)}")

@router.get("/indexation-factor")
async def get_indexation_factor(amount: float, end_work_date: str, to_date: Optional[str] = None):
    """
    קבלת מקדם הצמדה בלבד
    """
    try:
        indexed_amount = IndexationService.calculate_adjusted_amount(
            amount=amount,
            end_work_date=end_work_date,
            to_date=to_date
        )
        
        if indexed_amount is None:
            raise HTTPException(status_code=400, detail="לא ניתן לחשב הצמדה עבור התאריכים הנתונים")
        
        factor = indexed_amount / amount if amount > 0 else 1.0
        
        return {
            "original_amount": amount,
            "indexed_amount": indexed_amount,
            "indexation_factor": factor,
            "end_work_date": end_work_date,
            "to_date": to_date or date.today().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב מקדם הצמדה: {str(e)}")

@router.get("/work-ratio")
async def get_work_ratio(start_date: str, end_date: str, eligibility_date: str):
    """
    חישוב יחס עבודה בתוך 32 השנים האחרונות
    """
    try:
        ratio = IndexationService.work_ratio_within_last_32y(
            start_date=start_date,
            end_date=end_date,
            elig_date=eligibility_date
        )
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "eligibility_date": eligibility_date,
            "work_ratio": ratio,
            "percentage": f"{ratio * 100:.2f}%"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב יחס עבודה: {str(e)}")
