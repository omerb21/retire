"""
נקודות קצה API לקיבוע זכויות
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from datetime import date, datetime
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
            from app.services.retirement_age_service import calc_eligibility_date
            
            client_id = client_data["client_id"]
            
            with SessionLocal() as db:
                # טעינת לקוח
                client = db.query(Client).filter(Client.id == client_id).first()
                if not client:
                    raise HTTPException(status_code=404, detail="Client not found")
                
                # טעינת מענקים
                grants = db.query(Grant).filter(Grant.client_id == client_id).all()
                
                # בדיקה שיש מענקים
                if not grants:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "לא ניתן לחשב קיבוע זכויות",
                            "reasons": ["לא קיימים מענקי פיצויים ללקוח זה"],
                            "suggestion": "יש להוסיף מענקי פיצויים בטרם ביצוע חישוב קיבוע זכויות"
                        }
                    )
                
                # קביעת תאריך תחילת קצבה
                pension_start_date = client.pension_start_date
                
                # אם אין תאריך בטבלת Client, נחפש את התאריך המוקדם ביותר מהקצבאות
                if not pension_start_date:
                    from app.models.pension_fund import PensionFund
                    pension_funds = db.query(PensionFund).filter(
                        PensionFund.client_id == client_id,
                        PensionFund.pension_start_date.isnot(None)
                    ).all()
                    
                    if pension_funds:
                        # מציאת התאריך המוקדם ביותר
                        pension_start_date = min(fund.pension_start_date for fund in pension_funds)
                        print(f"DEBUG: Found earliest pension start date from funds: {pension_start_date}")
                
                # חישוב תאריך זכאות (גיל פרישה)
                eligibility_date = calc_eligibility_date(client.birth_date, client.gender)
                
                # בדיקת זכאות - האם הגיע לגיל פרישה והתחיל לקבל קצבה
                today = date.today()
                age_condition_ok = today >= eligibility_date
                pension_condition_ok = pension_start_date is not None and today >= pension_start_date
                eligible = age_condition_ok and pension_condition_ok
                
                # אם הלקוח לא זכאי, נחזיר שגיאה מפורטת
                if not eligible:
                    reasons = []
                    if not age_condition_ok:
                        reasons.append(f"טרם הגיע לגיל פרישה ({eligibility_date.strftime('%d/%m/%Y')})")
                    if not pension_condition_ok:
                        if not pension_start_date:
                            reasons.append("לא הוגדר תאריך תחילת קצבה")
                        else:
                            reasons.append(f"טרם התחיל לקבל קצבה ({pension_start_date.strftime('%d/%m/%Y')})")
                    
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "הלקוח אינו זכאי לקיבוע זכויות",
                            "reasons": reasons,
                            "eligibility_date": eligibility_date.isoformat(),
                            "age_condition_ok": age_condition_ok,
                            "pension_condition_ok": pension_condition_ok
                        }
                    )
                
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
                            "grant_date": grant.grant_date.isoformat() if hasattr(grant, 'grant_date') and grant.grant_date else None,
                            "employer_name": grant.employer_name
                        }
                        for grant in grants
                    ],
                    "eligibility_date": eligibility_date.isoformat(),
                    "eligibility_year": eligibility_date.year
                }
                
                print(f"DEBUG: Formatted data for service: {formatted_data}")
                result = calculate_full_fixation(formatted_data)
                print(f"DEBUG: Service result: {result}")
                
                # לא שומרים אוטומטית - רק מחזירים את התוצאות
                # השמירה תתבצע רק כאשר המשתמש לוחץ על "שמור"
                print(f"DEBUG: Calculation completed for client {client_id} - NOT saved to DB")
                
                return result
        else:
            # פורמט מפורט - שימוש ישיר
            result = calculate_full_fixation(client_data)
            return result
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is (they already have proper error messages)
        raise
    except ValueError as e:
        # Value errors usually indicate data problems
        logger.error(f"שגיאת נתונים בחישוב קיבוע זכויות: {e}")
        error_msg = str(e)
        
        # Translate common error messages to Hebrew
        if "birth_date" in error_msg.lower():
            error_msg = "תאריך לידה חסר או לא תקין"
        elif "gender" in error_msg.lower():
            error_msg = "מין הלקוח חסר או לא תקין"
        elif "grant" in error_msg.lower():
            error_msg = "נתוני מענק לא תקינים"
        elif "date" in error_msg.lower():
            error_msg = "אחד מהתאריכים אינו תקין"
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": "שגיאה בנתונים",
                "message": error_msg,
                "suggestion": "אנא בדוק שכל הנתונים הנדרשים קיימים ותקינים"
            }
        )
    except Exception as e:
        # General errors
        logger.error(f"שגיאה בחישוב קיבוע זכויות: {e}", exc_info=True)
        error_msg = str(e)
        
        # Try to provide more helpful error messages
        if "division by zero" in error_msg.lower():
            error_msg = "שגיאה בחישוב - ערך אפס לא צפוי"
        elif "none" in error_msg.lower():
            error_msg = "חסר נתון נדרש לחישוב"
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "שגיאה בחישוב קיבוע זכויות",
                "message": error_msg,
                "suggestion": "אנא פנה לתמיכה טכנית"
            }
        )

@router.post("/save")
async def save_rights_fixation(data: Dict[str, Any]):
    """
    שמירת תוצאות קיבוע זכויות ב-DB
    
    Body:
    {
        "client_id": 1,
        "calculation_result": { ... },
        "formatted_data": { ... }
    }
    """
    try:
        from app.database import SessionLocal
        from app.models.fixation_result import FixationResult
        from datetime import datetime
        
        client_id = data.get("client_id")
        result = data.get("calculation_result")
        formatted_data = data.get("formatted_data")
        
        if not client_id or not result:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        with SessionLocal() as db:
            # Check if there's an existing result and update, or create new
            existing = db.query(FixationResult).filter(
                FixationResult.client_id == client_id
            ).order_by(FixationResult.created_at.desc()).first()
            
            if existing:
                # Update existing record
                existing.raw_result = result
                existing.raw_payload = formatted_data
                existing.exempt_capital_remaining = result.get("exemption_summary", {}).get("remaining_exempt_capital", 0)
                existing.created_at = datetime.now()
            else:
                # Create new record
                fixation_record = FixationResult(
                    client_id=client_id,
                    created_at=datetime.now(),
                    exempt_capital_remaining=result.get("exemption_summary", {}).get("remaining_exempt_capital", 0),
                    used_commutation=0.0,
                    raw_payload=formatted_data,
                    raw_result=result,
                    notes="Saved via rights_fixation service"
                )
                db.add(fixation_record)
            
            db.commit()
            
            return {
                "success": True,
                "message": "תוצאות קיבוע הזכויות נשמרו בהצלחה",
                "calculation_date": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"שגיאה בשמירת קיבוע זכויות: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בשמירה: {str(e)}")

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

@router.get("/client/{client_id}")
async def get_saved_fixation(client_id: int):
    """
    קבלת תוצאות קיבוע זכויות שמורות עבור לקוח
    """
    try:
        from app.database import SessionLocal
        from app.models.fixation_result import FixationResult
        
        with SessionLocal() as db:
            result = db.query(FixationResult).filter(
                FixationResult.client_id == client_id
            ).order_by(FixationResult.created_at.desc()).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="לא נמצאו תוצאות קיבוע זכויות שמורות")
            
            return {
                "success": True,
                "calculation_date": result.created_at.isoformat(),
                "exempt_capital_remaining": result.exempt_capital_remaining,
                "raw_result": result.raw_result,
                "raw_payload": result.raw_payload
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"שגיאה בטעינת קיבוע זכויות: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בטעינה: {str(e)}")

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
