"""
מודול זכאות לקיבוע זכויות - מקור האמת היחיד לתנאי זכאות
"""
from datetime import date
from dateutil.relativedelta import relativedelta

# ייבוא שירות חישוב גיל פרישה דינמי
try:
    from app.services.retirement_age_service import get_retirement_date
    USE_DYNAMIC_RETIREMENT_AGE = True
except ImportError:
    # fallback למקרה שהשירות לא זמין
    USE_DYNAMIC_RETIREMENT_AGE = False
    ELIG_AGE_MALE = 67
    ELIG_AGE_FEMALE = 62

def calc_eligibility_date(birthdate: date, gender: str) -> date:
    """חישוב תאריך זכאות לקיבוע זכויות לפי מין וגיל - משתמש בשירות גיל פרישה דינמי"""
    if USE_DYNAMIC_RETIREMENT_AGE:
        # שימוש בשירות הדינמי שמחשב לפי טבלת החוק
        return get_retirement_date(birthdate, gender)
    else:
        # fallback לחישוב ישן (למקרה שהשירות לא זמין)
        g = (gender or "").strip().lower()
        if g in {"male", "m", "זכר"}:
            return birthdate + relativedelta(years=ELIG_AGE_MALE)
        elif g in {"female", "f", "נקבה"}:
            return birthdate + relativedelta(years=ELIG_AGE_FEMALE)
        # ברירת מחדל שמרנית אם לא ידוע - נחשב לפי גבר
        return birthdate + relativedelta(years=ELIG_AGE_MALE)

def has_started_pension(pension_start_date: date | None, today: date | None = None) -> bool:
    """בדיקה האם התחיל לקבל קצבה"""
    if not pension_start_date:
        return False
    today = today or date.today()
    return pension_start_date <= today

def is_eligible_for_fixation(birthdate: date, gender: str, pension_start_date: date | None, today: date | None = None):
    """בדיקת זכאות מלאה לקיבוע זכויות
    
    שנת הזכאות היא המאוחר מבין:
    1. תאריך הגעה לגיל פרישה
    2. תאריך תחילת קצבה ראשונה
    """
    today = today or date.today()
    age_eligibility_date = calc_eligibility_date(birthdate, gender)
    
    # שנת הזכאות האמיתית היא המאוחר מבין גיל הפרישה לתחילת הקצבה
    if pension_start_date and pension_start_date > age_eligibility_date:
        actual_eligibility_date = pension_start_date
    else:
        actual_eligibility_date = age_eligibility_date
    
    cond_age = today >= age_eligibility_date
    cond_pension = has_started_pension(pension_start_date, today)
    
    return {
        "eligible": bool(cond_age and cond_pension),
        "eligibility_date": actual_eligibility_date,  # תאריך הזכאות האמיתי
        "age_condition_ok": bool(cond_age),
        "pension_condition_ok": bool(cond_pension)
    }
