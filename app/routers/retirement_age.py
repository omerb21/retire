"""
API endpoints for retirement age settings and calculations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import date

from app.services.retirement_age_service import (
    calculate_retirement_age,
    get_retirement_age_simple,
    get_retirement_date,
    load_retirement_age_settings,
    save_retirement_age_settings
)

router = APIRouter(prefix="/retirement-age", tags=["retirement-age"])


class RetirementAgeRequest(BaseModel):
    birth_date: date
    gender: str


class RetirementAgeSettings(BaseModel):
    male_retirement_age: int = 67
    use_legal_table_for_women: bool = True
    female_retirement_age: Optional[int] = None  # רק אם לא משתמשים בטבלה


@router.post("/calculate")
def calculate_retirement_age_endpoint(request: RetirementAgeRequest):
    """
    חישוב גיל פרישה מדויק לפי תאריך לידה ומגדר
    """
    try:
        result = calculate_retirement_age(request.birth_date, request.gender)
        return {
            "age_years": result["age_years"],
            "age_months": result["age_months"],
            "retirement_date": result["retirement_date"].isoformat(),
            "source": result["source"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calculate-simple")
def calculate_retirement_age_simple_endpoint(request: RetirementAgeRequest):
    """
    חישוב גיל פרישה בשנים שלמות (לתאימות לאחור)
    """
    try:
        age = get_retirement_age_simple(request.birth_date, request.gender)
        retirement_date = get_retirement_date(request.birth_date, request.gender)
        return {
            "retirement_age": age,
            "retirement_date": retirement_date.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings")
def get_retirement_age_settings():
    """
    קבלת הגדרות גיל פרישה נוכחיות
    """
    try:
        settings = load_retirement_age_settings()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
def update_retirement_age_settings(settings: RetirementAgeSettings):
    """
    עדכון הגדרות גיל פרישה
    """
    try:
        settings_dict = settings.dict()
        success = save_retirement_age_settings(settings_dict)
        
        if success:
            return {"message": "הגדרות גיל הפרישה עודכנו בהצלחה", "settings": settings_dict}
        else:
            raise HTTPException(status_code=500, detail="שגיאה בשמירת ההגדרות")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
