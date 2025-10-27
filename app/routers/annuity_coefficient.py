"""
API endpoints למקדמי קצבה
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import logging

from app.services.annuity_coefficient_service import get_annuity_coefficient

logger = logging.getLogger(__name__)
router = APIRouter()


class AnnuityCoefficientRequest(BaseModel):
    """בקשה לחישוב מקדם קצבה"""
    product_type: str
    start_date: str  # ISO format YYYY-MM-DD (תאריך התחלת תכנית - לזיהוי דור)
    gender: str
    retirement_age: int
    company_name: Optional[str] = None
    option_name: Optional[str] = None
    survivors_option: Optional[str] = None
    spouse_age_diff: int = 0
    target_year: Optional[int] = None
    birth_date: Optional[str] = None  # ISO format YYYY-MM-DD (לחישוב גיל בפועל)
    pension_start_date: Optional[str] = None  # ISO format YYYY-MM-DD (תאריך מימוש)


class AnnuityCoefficientResponse(BaseModel):
    """תגובה עם מקדם קצבה"""
    factor_value: float
    source_table: str
    source_keys: dict
    target_year: Optional[int]
    guarantee_months: Optional[int]
    notes: str


@router.post("/calculate", response_model=AnnuityCoefficientResponse)
async def calculate_annuity_coefficient(request: AnnuityCoefficientRequest):
    """
    מחשב מקדם קצבה לפי פרמטרים
    """
    try:
        # המרת תאריכים
        start_date_obj = date.fromisoformat(request.start_date)
        birth_date_obj = date.fromisoformat(request.birth_date) if request.birth_date else None
        pension_start_date_obj = date.fromisoformat(request.pension_start_date) if request.pension_start_date else None
        
        # חישוב מקדם
        result = get_annuity_coefficient(
            product_type=request.product_type,
            start_date=start_date_obj,
            gender=request.gender,
            retirement_age=request.retirement_age,
            company_name=request.company_name,
            option_name=request.option_name,
            survivors_option=request.survivors_option,
            spouse_age_diff=request.spouse_age_diff,
            target_year=request.target_year,
            birth_date=birth_date_obj,
            pension_start_date=pension_start_date_obj
        )
        
        logger.info(f"[API מקדם קצבה] חושב מקדם: {result['factor_value']}")
        
        return AnnuityCoefficientResponse(**result)
        
    except ValueError as e:
        logger.error(f"[API מקדם קצבה] שגיאת ולידציה: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API מקדם קצבה] שגיאה: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/status")
async def get_tables_status():
    """
    בודק סטטוס טבלאות המקדמים
    """
    from app.database import get_db
    from sqlalchemy import text
    
    db = next(get_db())
    
    try:
        tables = [
            'policy_generation_coefficient',
            'product_to_generation_map',
            'company_annuity_coefficient',
            'pension_fund_coefficient'
        ]
        
        status = {}
        for table in tables:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
            status[table] = result[0] if result else 0
        
        return {
            'status': 'ok',
            'tables': status,
            'total_records': sum(status.values())
        }
        
    except Exception as e:
        logger.error(f"[API מקדם קצבה] שגיאה בבדיקת סטטוס: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
