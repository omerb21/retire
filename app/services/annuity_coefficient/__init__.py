"""
שירות לחישוב מקדמי קצבה דינמיים לפי סוג מוצר, גיל ומגדר
Updated: 2025-11-04
"""

from datetime import date, datetime
from typing import Optional, Dict, Any
import logging
from .utils import normalize_gender, is_pension_fund
from .pension_fund import get_pension_fund_coefficient
from .insurance import get_insurance_coefficient

logger = logging.getLogger(__name__)
# Force reload: 2025-11-04 15:35


def get_annuity_coefficient(
    product_type: str,
    start_date: date,
    gender: str,
    retirement_age: int,
    company_name: Optional[str] = None,
    option_name: Optional[str] = None,
    survivors_option: Optional[str] = None,
    spouse_age_diff: int = 0,
    target_year: Optional[int] = None,
    birth_date: Optional[date] = None,
    pension_start_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    מחשב מקדם קצבה לפי סוג מוצר ופרמטרים

    Args:
        product_type: סוג המוצר (קרן פנסיה / ביטוח מנהלים)
        start_date: תאריך התחלת הפוליסה/תכנית (לזיהוי דור)
        gender: מגדר (זכר/נקבה/M/F)
        retirement_age: גיל פרישה (fallback אם אין birth_date)
        company_name: שם חברה (אופציונלי)
        option_name: שם מסלול (אופציונלי)
        survivors_option: מסלול שארים (לקרן פנסיה)
        spouse_age_diff: הפרש גיל בן זוג (לקרן פנסיה)
        target_year: שנת יעד לחישוב (אם לא מסופק - שנה נוכחית)
        birth_date: תאריך לידה (לחישוב גיל בפועל)
        pension_start_date: תאריך תחילת קצבה (תאריך מימוש)

    Returns:
        Dict עם:
        - factor_value: ערך המקדם
        - source_table: טבלת המקור
        - source_keys: מפתחות החיפוש
        - target_year: שנת היעד
        - guarantee_months: חודשי הבטחה (אם רלוונטי)
        - notes: הערות
    """

    # נרמול מגדר
    sex = normalize_gender(gender)

    # חישוב גיל בפועל בתאריך תחילת הקצבה
    actual_age = retirement_age  # ברירת מחדל
    if birth_date and pension_start_date:
        # חישוב גיל מדויק בתאריך תחילת הקצבה
        age_years = pension_start_date.year - birth_date.year
        # התאמה אם עדיין לא היה יום הולדת השנה
        if (pension_start_date.month, pension_start_date.day) < (
            birth_date.month,
            birth_date.day,
        ):
            age_years -= 1
        actual_age = age_years
        logger.info(
            f"[מקדם קצבה] גיל מחושב: {actual_age} "
            f"(לידה: {birth_date}, תחילת קצבה: {pension_start_date})"
        )

    # שנת יעד
    if target_year is None:
        target_year = datetime.now().year

    # בדיקה אם זו קרן פנסיה
    if is_pension_fund(product_type):
        logger.info(
            f"🔵 [DEBUG] Product is pension fund, calling get_pension_fund_coefficient "
            f"with survivors_option='{survivors_option or 'תקנוני'}'"
        )
        return get_pension_fund_coefficient(
            sex=sex,
            retirement_age=actual_age,
            survivors_option=survivors_option or "תקנוני",
            spouse_age_diff=spouse_age_diff,
        )

    # אחרת - ביטוח מנהלים
    return get_insurance_coefficient(
        start_date=start_date,
        sex=sex,
        age=actual_age,
        company_name=company_name,
        option_name=option_name,
        target_year=target_year,
    )


__all__ = ["get_annuity_coefficient"]
