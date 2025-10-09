"""
נקודות קצה API לקיבוע זכויות
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from datetime import date
import logging

from app.services.rights_fixation import (
    calculate_full_fixation,
    compute_grant_effect,
    compute_client_exemption,
    calculate_eligibility_age,
    get_monthly_cap,
    get_exemption_percentage,
    calc_exempt_capital
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rights-fixation", tags=["rights_fixation"])

@router.post("/calculate")
async def calculate_rights_fixation(client_data: Dict[str, Any]):
    """
    חישוב קיבוע זכויות מלא עבור לקוח
    
    Body format 1 (client_id):
    {
        "client_id": 1
    }
    
    Body format 2 (detailed):
    {
        "grants": [
            {
                "grant_amount": 100000,
                "work_start_date": "2010-01-01",
                "work_end_date": "2020-12-31",
                "employer_name": "חברה א'"
            }
        ],
        "eligibility_date": "2025-01-01",
        "eligibility_year": 2025
    }
    """
    try:
        print(f"DEBUG: Rights fixation router called with: {client_data}")
        
        # אם זה client_id, נטען את הנתונים מהמסד
        if "client_id" in client_data and "grants" not in client_data:
            from app.database import SessionLocal
            from app.models.client import Client
            from app.models.grant import Grant
            from datetime import date
            
            client_id = client_data["client_id"]
            
            with SessionLocal() as db:
                # טעינת לקוח
                client = db.query(Client).filter(Client.id == client_id).first()
                if not client:
                    raise HTTPException(status_code=404, detail="Client not found")
                
                # טעינת מענקים
                grants = db.query(Grant).filter(Grant.client_id == client_id).all()
                
                # הכנת נתונים לשירות
                formatted_data = {
                    "id": client_id,
                    "birth_date": client.birth_date.isoformat() if client.birth_date else None,
                    "gender": client.gender,
                    "grants": [
                        {
                            "grant_amount": grant.grant_amount,
                            "work_start_date": grant.work_start_date.isoformat() if grant.work_start_date else None,
                            "work_end_date": grant.work_end_date.isoformat() if grant.work_end_date else None,
                            "employer_name": grant.employer_name
                        }
                        for grant in grants
                    ],
                    "eligibility_date": date.today().isoformat(),
                    "eligibility_year": date.today().year
                }
                
                print(f"DEBUG: Formatted data for service: {formatted_data}")
                result = calculate_full_fixation(formatted_data)
                print(f"DEBUG: Service result: {result}")
                return result
        else:
            # פורמט מפורט - שימוש ישיר
            result = calculate_full_fixation(client_data)
            return result
            
    except Exception as e:
        logger.error(f"שגיאה בחישוב קיבוע זכויות: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב: {str(e)}")

@router.post("/grant/effect")
async def calculate_grant_effect(grant_data: Dict[str, Any]):
    """
    חישוב השפעת מענק בודד על ההון הפטור
    
    Body:
    {
        "grant_amount": 100000,
        "work_start_date": "2010-01-01", 
        "work_end_date": "2020-12-31",
        "eligibility_date": "2025-01-01"
    }
    """
    try:
        eligibility_date = grant_data.pop('eligibility_date')
        effect = compute_grant_effect(grant_data, eligibility_date)
        
        if effect is None:
            raise HTTPException(status_code=400, detail="כשל בחישוב השפעת המענק")
            
        return effect
    except Exception as e:
        logger.error(f"שגיאה בחישוב השפעת מענק: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב: {str(e)}")

@router.post("/exemption/summary")
async def calculate_exemption_summary(data: Dict[str, Any]):
    """
    חישוב סיכום פטור עבור רשימת מענקים
    
    Body:
    {
        "grants": [
            {
                "impact_on_exemption": 135000
            }
        ],
        "eligibility_year": 2025
    }
    """
    try:
        grants = data.get('grants', [])
        eligibility_year = data.get('eligibility_year', 2025)
        
        summary = compute_client_exemption(grants, eligibility_year)
        return summary
    except Exception as e:
        logger.error(f"שגיאה בחישוב סיכום פטור: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בחישוב: {str(e)}")

@router.get("/caps/{year}")
async def get_caps_for_year(year: int):
    """
    קבלת תקרות ואחוזי פטור לשנה מסוימת
    """
    try:
        return {
            "year": year,
            "monthly_cap": get_monthly_cap(year),
            "exemption_percentage": get_exemption_percentage(year),
            "exempt_capital": calc_exempt_capital(year)
        }
    except Exception as e:
        logger.error(f"שגיאה בקבלת תקרות לשנה {year}: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בקבלת נתונים: {str(e)}")

@router.post("/eligibility-date")
async def calculate_eligibility_date(data: Dict[str, Any]):
    """
    חישוב תאריך זכאות על בסיס גיל ומגדר
    
    Body:
    {
        "birth_date": "1960-01-01",
        "gender": "male",
        "pension_start": "2025-01-01"
    }
    """
    try:
        from datetime import datetime
        
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
        gender = data['gender']
        pension_start = datetime.strptime(data['pension_start'], '%Y-%m-%d').date()
        
        eligibility_date = calculate_eligibility_age(birth_date, gender, pension_start)
        
        return {
            "eligibility_date": eligibility_date.isoformat(),
            "eligibility_year": eligibility_date.year
        }
    except Exception as e:
        logger.error(f"שגיאה בחישוב תאריך זכאות: {e}")
        raise HTTPException(status_code=400, detail=f"שגיאה בחישוב: {str(e)}")

@router.get("/test")
async def test_cbs_api():
    """
    בדיקת חיבור ל-API של הלמ"ס
    """
    try:
        from app.services.rights_fixation import calculate_adjusted_amount
        
        # בדיקה עם נתונים לדוגמה
        test_amount = 100000
        test_date = "2020-01-01"
        
        result = calculate_adjusted_amount(test_amount, test_date)
        
        return {
            "status": "success" if result else "failed",
            "test_amount": test_amount,
            "test_date": test_date,
            "indexed_amount": result
        }
    except Exception as e:
        logger.error(f"שגיאה בבדיקת API: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
