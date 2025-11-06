"""
מודול חישוב יחס עבודה - חישוב יחס החלקיות של 32 השנים האחרונות
"""
from datetime import datetime, date, timedelta
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


def work_ratio_within_last_32y(
    start_date: Union[str, date], 
    end_date: Union[str, date], 
    elig_date: Union[str, date], 
    birth_date: Optional[Union[str, date]] = None, 
    gender: Optional[str] = None
) -> float:
    """
    מחשב את היחס של ימי העבודה בין start_date ל-end_date שנופלים
    בתוך 32 השנים שקדמו ל-elig_date, ומוגבל עד גיל הפרישה.
    
    :param start_date: תאריך תחילת עבודה
    :param end_date: תאריך סיום עבודה
    :param elig_date: תאריך זכאות
    :param birth_date: תאריך לידה (אופציונלי - לחישוב גיל פרישה)
    :param gender: מגדר (אופציונלי - לחישוב גיל פרישה)
    :return: יחס בין 0 ל-1
    """
    try:
        # המרת תאריכים לאובייקטי date אם הם מחרוזות
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        if isinstance(elig_date, str):
            elig_date = datetime.strptime(elig_date, '%Y-%m-%d').date()
        if birth_date and isinstance(birth_date, str):
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            
        # חישוב תאריך גיל פרישה אם ניתנו נתוני לקוח
        retirement_date = None
        if birth_date and gender:
            try:
                # שימוש בשירות גיל פרישה דינמי
                from app.services.retirement_age_service import get_retirement_date
                retirement_date = get_retirement_date(birth_date, gender)
                logger.info(f"[יחסי מענק] גיל פרישה מחושב: {retirement_date} (מגדר: {gender})")
            except Exception as e:
                logger.warning(f"[יחסי מענק] שגיאה בחישוב גיל פרישה: {e}")
                # fallback לחישוב פשוט
                retirement_age = 67 if gender.lower() in ['m', 'male', 'זכר'] else 65
                retirement_date = date(birth_date.year + retirement_age, birth_date.month, birth_date.day)
        
        # הגבלת תאריך סיום העבודה לגיל הפרישה
        effective_end_date = end_date
        if retirement_date and end_date > retirement_date:
            effective_end_date = retirement_date
            logger.info(f"[יחסי מענק] הגבלת תאריך סיום מ-{end_date} ל-{effective_end_date} (גיל פרישה)")
            
        # חישוב חלון 32 השנים
        limit_start = elig_date - timedelta(days=int(365.25 * 32))
        
        # חישוב ימי עבודה כוללים - משתמשים בתאריך המקורי end_date (לא effective_end_date)
        # זה חשוב לחישוב היחס הנכון: אם עבודה הסתיימה אחרי גיל פרישה, 
        # היחס יהיה קטן יותר כי חלק מהעבודה לא נחשב
        total_days = (end_date - start_date).days
        if total_days <= 0:
            logger.info(f"[יחסי מענק] אין ימי עבודה רלוונטיים")
            return 0.0
            
        # חישוב חפיפה עם חלון 32 השנים (מוגבל לגיל פרישה)
        overlap_start = max(start_date, limit_start)
        overlap_end = min(effective_end_date, elig_date)
        overlap_days = max((overlap_end - overlap_start).days, 0)
        
        # חישוב יחס: חפיפה בפועל / סה"כ ימי עבודה
        # אם עבודה הסתיימה אחרי גיל פרישה, overlap_end יהיה קטן יותר, ולכן היחס יהיה קטן יותר
        ratio = overlap_days / total_days if total_days > 0 else 0
        
        # גבולות [0, 1]
        ratio = min(max(ratio, 0), 1)
        
        logger.info(f"[יחסי מענק] תאריך ייחוס={elig_date}, התחלה={start_date}, "
                   f"סיום מקורי={end_date}, סיום אפקטיבי={effective_end_date}, "
                   f"חפיפה={overlap_days} ימים, יחס={ratio:.4f}")
        
        return ratio
        
    except Exception as e:
        logger.error(f"[שגיאה ביחס מענק] התחלה={start_date}, סיום={end_date}, שגיאה: {str(e)}")
        return 0.0


def ratio_last_32y(
    start_date: Union[str, date], 
    end_date: Union[str, date], 
    eligibility_date: Union[str, date]
) -> float:
    """
    פונקציה לתאימות לאחור - מאצילה ל-work_ratio_within_last_32y
    """
    return work_ratio_within_last_32y(start_date, end_date, eligibility_date)
