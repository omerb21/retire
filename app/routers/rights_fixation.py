"""
נקודות קצה API לקיבוע זכויות
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from datetime import date, datetime
import logging

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.grant import Grant
from app.models.fixation_result import FixationResult
from app.services.rights_fixation import (
    calculate_full_fixation,
    compute_grant_effect,
    compute_client_exemption,
    calculate_eligibility_age,
    get_monthly_cap,
    get_exemption_percentage,
    calc_exempt_capital
)
from app.services.retirement.utils.pension_utils import get_effective_pension_start_date
from app.services.retirement_age_service import calc_eligibility_date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rights-fixation", tags=["rights_fixation"])


def calculate_and_save_fixation_for_client(db: Session, client_id: int) -> Optional[FixationResult]:
    """Compute and persist rights fixation for a client using an existing DB session.

    This helper mirrors the logic of the /calculate and /save endpoints and is
    intended for internal server-side flows (e.g. retirement scenario execution)
    to simulate clicking "calculate" + "save" on the fixation screen.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.warning(f"Rights fixation: client {client_id} not found, skipping auto-fixation")
        return None

    grants = db.query(Grant).filter(Grant.client_id == client_id).all()

    # Determine effective pension start date from actual pensions
    pension_start_date = get_effective_pension_start_date(db, client)

    # Determine statutory eligibility date (retirement date)
    eligibility_date = calc_eligibility_date(client.birth_date, client.gender) if client.birth_date and client.gender else None

    # For internal flows (e.g. retirement scenarios) we always calculate and persist fixation,
    # even if the client is not yet "eligible" by today's date, so we deliberately
    # do NOT enforce the age/pension start date conditions here.
    today = date.today()

    # Build formatted data similar to the /calculate endpoint (client_id branch)
    eligibility_date_to_use = eligibility_date or today
    formatted_data: Dict[str, Any] = {
        "id": client_id,
        "birth_date": client.birth_date.isoformat() if client.birth_date else None,
        "gender": client.gender,
        "grants": [
            {
                "grant_amount": grant.grant_amount,
                "work_start_date": grant.work_start_date.isoformat() if grant.work_start_date else None,
                "work_end_date": grant.work_end_date.isoformat() if grant.work_end_date else None,
                "grant_date": grant.grant_date.isoformat() if getattr(grant, "grant_date", None) else None,
                "employer_name": grant.employer_name,
            }
            for grant in grants
        ],
        "eligibility_date": eligibility_date_to_use.isoformat(),
        "eligibility_year": eligibility_date_to_use.year,
        "effective_pension_start_date": pension_start_date.isoformat() if pension_start_date else None,
    }

    logger.info("Rights fixation: calculating full fixation for client %s", client_id)
    result = calculate_full_fixation(formatted_data)

    # If calculation failed, do not save a broken result
    if not isinstance(result, dict) or result.get("error"):
        logger.error("Rights fixation: calculation failed for client %s with error: %s", client_id, result.get("error"))
        return None

    exemption_summary = result.get("exemption_summary", {}) or {}
    remaining_exempt_capital = exemption_summary.get("remaining_exempt_capital", 0) or 0.0

    # Upsert FixationResult for this client using the same semantics as /save
    existing = (
        db.query(FixationResult)
        .filter(FixationResult.client_id == client_id)
        .order_by(FixationResult.created_at.desc())
        .first()
    )

    now = datetime.now()

    if existing:
        existing.raw_result = result
        existing.raw_payload = formatted_data
        existing.exempt_capital_remaining = remaining_exempt_capital
        existing.created_at = now
        fixation_record = existing
    else:
        fixation_record = FixationResult(
            client_id=client_id,
            created_at=now,
            exempt_capital_remaining=remaining_exempt_capital,
            used_commutation=0.0,
            raw_payload=formatted_data,
            raw_result=result,
            notes="Saved automatically during retirement scenario execution",
        )
        db.add(fixation_record)

    db.flush()
    logger.info("Rights fixation: auto-fixation saved for client %s (remaining_exempt_capital=%.2f)", client_id, remaining_exempt_capital)
    return fixation_record


def update_fixation_exempt_pension_fields(fixation: FixationResult) -> None:
    """Update exempt pension-related fields on a FixationResult record.

    This helper is intended for server-side flows (e.g. retirement scenario execution)
    to simulate the pension-exemption part of pressing the "save" button in the
    fixation UI, based on the current exempt_capital_remaining.
    """
    try:
        raw_result = fixation.raw_result or {}
        if not isinstance(raw_result, dict):
            return

        exemption_summary = raw_result.get("exemption_summary") or {}
        if not isinstance(exemption_summary, dict):
            exemption_summary = {}

        exempt_capital_initial = float(exemption_summary.get("exempt_capital_initial") or 0.0)
        remaining_exempt_capital = float(getattr(fixation, "exempt_capital_remaining", 0.0) or 0.0)

        eligibility_year = (
            raw_result.get("eligibility_year")
            or exemption_summary.get("eligibility_year")
        )
        try:
            eligibility_year_int = int(eligibility_year) if eligibility_year is not None else None
        except (TypeError, ValueError):
            eligibility_year_int = None

        if eligibility_year_int is None:
            logger.warning(
                "Rights fixation: cannot update exempt pension fields for fixation %s - missing eligibility_year",
                getattr(fixation, "id", None),
            )
            return

        if exempt_capital_initial > 0:
            exemption_percentage = remaining_exempt_capital / exempt_capital_initial
        else:
            exemption_percentage = 0.0

        pension_ceiling = get_monthly_cap(eligibility_year_int)
        if pension_ceiling > 0:
            exempt_pension_percentage = (remaining_exempt_capital / 180.0) / pension_ceiling
            remaining_monthly_exemption = round(exempt_pension_percentage * pension_ceiling, 2)
        else:
            exempt_pension_percentage = 0.0
            remaining_monthly_exemption = 0.0

        # Update summary fields in a way compatible with the frontend "save" logic
        exemption_summary["eligibility_year"] = eligibility_year_int
        exemption_summary["exempt_capital_initial"] = exempt_capital_initial
        exemption_summary["remaining_exempt_capital"] = remaining_exempt_capital
        exemption_summary["exemption_percentage"] = exemption_percentage
        exemption_summary["remaining_monthly_exemption"] = remaining_monthly_exemption
        exemption_summary["exempt_pension_percentage"] = exempt_pension_percentage

        # Optional diagnostic fields used by documents/reports
        used_commutation = float(getattr(fixation, "used_commutation", 0.0) or 0.0)
        exemption_summary["total_commutations"] = used_commutation
        exemption_summary["final_remaining_exemption"] = remaining_exempt_capital

        raw_result["exemption_summary"] = exemption_summary
        fixation.raw_result = raw_result

        logger.info(
            "Rights fixation: updated exempt pension fields for fixation %s (remaining_exempt_capital=%.2f, exempt_pension_percentage=%.4f)",
            getattr(fixation, "id", None),
            remaining_exempt_capital,
            exempt_pension_percentage,
        )
    except Exception as e:
        logger.error(
            "Rights fixation: failed to update exempt pension fields for fixation %s: %s",
            getattr(fixation, "id", None),
            e,
        )

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
                
                # טעינת מענקים (אופציונלי - ניתן לחשב קיבוע זכויות גם ללא מענקים)
                grants = db.query(Grant).filter(Grant.client_id == client_id).all()
                
                # קביעת תאריך תחילת קצבה (אחיד דרך פונקציית עזר)
                pension_start_date = get_effective_pension_start_date(db, client)
                
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
                    "eligibility_year": eligibility_date.year,
                    "effective_pension_start_date": pension_start_date.isoformat() if pension_start_date else None,
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
        from app.models.client import Client
        from datetime import datetime
        
        client_id = data.get("client_id")
        result = data.get("calculation_result")
        formatted_data = data.get("formatted_data") or {}
        
        if not client_id or not result:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Ensure formatted_data is a mutable dict
        if not isinstance(formatted_data, dict):
            formatted_data = dict(formatted_data)
        
        with SessionLocal() as db:
            # Compute effective pension start date on save, so it's always present in the payload
            client = db.query(Client).filter(Client.id == client_id).first()
            effective_pension_start_date = get_effective_pension_start_date(db, client)
            formatted_data["effective_pension_start_date"] = (
                effective_pension_start_date.isoformat() if effective_pension_start_date else None
            )

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
        from app.models.client import Client
        from app.services.retirement_age_service import calc_eligibility_date
        
        with SessionLocal() as db:
            result = db.query(FixationResult).filter(
                FixationResult.client_id == client_id
            ).order_by(FixationResult.created_at.desc()).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="לא נמצאו תוצאות קיבוע זכויות שמורות")

            # Ensure exemption_summary includes derived exempt pension fields so
            # that reports behave as if the user pressed the "save" button in
            # the fixation UI. This also acts as a lazy migration for existing
            # records created before server-side flows updated these fields.
            try:
                raw = result.raw_result or {}
                if isinstance(raw, dict):
                    exemption_summary = raw.get("exemption_summary") or {}
                    needs_update = (
                        not isinstance(exemption_summary, dict)
                        or "exempt_pension_percentage" not in exemption_summary
                        or "remaining_monthly_exemption" not in exemption_summary
                    )
                    if needs_update:
                        update_fixation_exempt_pension_fields(result)
            except Exception as e:
                logger.error(
                    "Rights fixation: failed to lazily update exempt pension fields for client %s: %s",
                    client_id,
                    e,
                )
            
            # Compute current eligibility status (same logic as /calculate)
            client = db.query(Client).filter(Client.id == client_id).first()
            eligible = False
            if client and client.birth_date and client.gender:
                pension_start_date = get_effective_pension_start_date(db, client)
                eligibility_date = calc_eligibility_date(client.birth_date, client.gender)
                today = date.today()
                age_condition_ok = today >= eligibility_date
                pension_condition_ok = pension_start_date is not None and today >= pension_start_date
                eligible = age_condition_ok and pension_condition_ok
            
            return {
                "success": True,
                "calculation_date": result.created_at.isoformat(),
                "exempt_capital_remaining": result.exempt_capital_remaining,
                "raw_result": result.raw_result,
                "raw_payload": result.raw_payload,
                "eligible": eligible,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"שגיאה בטעינת קיבוע זכויות: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בטעינה: {str(e)}")


@router.delete("/client/{client_id}")
async def delete_fixation(client_id: int):
    """מחיקת תוצאות קיבוע זכויות שמורות עבור לקוח.

    הפעולה מוחקת את הרשומות מטבלת fixation_result עבור הלקוח,
    כך שנתוני קיבוע לא ישמשו יותר בחישובי קצבה פטורה ובדוחות.
    """
    try:
        from app.database import SessionLocal
        from app.models.fixation_result import FixationResult

        with SessionLocal() as db:
            deleted = (
                db.query(FixationResult)
                .filter(FixationResult.client_id == client_id)
                .delete(synchronize_session=False)
            )
            db.commit()

            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail="לא נמצאו תוצאות קיבוע זכויות למחיקה עבור לקוח זה",
                )

            return {
                "success": True,
                "message": "תוצאות קיבוע הזכויות נמחקו בהצלחה",
                "deleted_rows": deleted,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"שגיאה במחיקת קיבוע זכויות: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה במחיקת קיבוע זכויות: {str(e)}",
        )

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
