"""
מודול זכאות לקיבוע זכויות - מקור האמת היחיד לתנאי זכאות
"""
from datetime import date
from dateutil.relativedelta import relativedelta

ELIG_AGE_MALE = 67
ELIG_AGE_FEMALE = 62

def calc_eligibility_date(birthdate: date, gender: str) -> date:
    """חישוב תאריך זכאות לקיבוע זכויות לפי מין וגיל"""
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
    """בדיקת זכאות מלאה לקיבוע זכויות"""
    today = today or date.today()
    elig_date = calc_eligibility_date(birthdate, gender)
    cond_age = today >= elig_date
    cond_pension = has_started_pension(pension_start_date, today)
    return {
        "eligible": bool(cond_age and cond_pension),
        "eligibility_date": elig_date,
        "age_condition_ok": bool(cond_age),
        "pension_condition_ok": bool(cond_pension)
    }
