"""
שירות קיבוע זכויות - מימוש מלא על בסיס המערכת הקיימת
מבוסס על הלוגיקה מתוך תיקיית "מערכת קיבוע זכויות"
"""
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ========== 1. הצמדה למדד CBS ==========

# CBS Consumer Price Index API endpoint
CBS_CPI_API = "https://api.cbs.gov.il/index/data/calculator/120010"

def calculate_adjusted_amount(amount: float, end_work_date: Union[str, date], to_date: Optional[Union[str, date]] = None) -> Optional[float]:
    """
    מחשב את הסכום המוצמד לפי API של הלמ"ס
    
    :param amount: סכום נומינלי להצמדה
    :param end_work_date: תאריך סיום עבודה (YYYY-MM-DD)
    :param to_date: תאריך יעד להצמדה (אם None, ישתמש בתאריך נוכחי)
    :return: סכום מוצמד או None בשגיאה
    """
    try:
        # וידוא שהתאריכים מועברים כמחרוזות בפורמט YYYY-MM-DD
        if isinstance(end_work_date, date):
            end_work_date = end_work_date.isoformat()
        if to_date and isinstance(to_date, date):
            to_date = to_date.isoformat()
            
        params = {
            'value': amount, 
            'date': end_work_date,
            'toDate': to_date if to_date else datetime.today().date().isoformat(), 
            'format': 'json', 
            'download': 'false'
        }
        
        response = requests.get(CBS_CPI_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        answer = data.get('answer')
        if not answer:
            logger.warning(f'אזהרה: API ללא answer עבור {end_work_date} | תשובה: {data}')
            return None
            
        to_value = answer.get('to_value')
        if to_value is None:
            logger.warning(f'אזהרה: אין to_value עבור {end_work_date} | תשובה: {data}')
            return None
            
        return round(float(to_value), 2)
        
    except Exception as e:
        logger.error(f'שגיאה בהצמדה עבור {end_work_date}: {e}')
        return None

def index_grant(amount: float, start_date: Union[str, date], end_work_date: Union[str, date], elig_date: Optional[Union[str, date]] = None) -> Optional[float]:
    """
    פונקציה עוטפת להצמדת מענק
    
    :param amount: סכום נומינלי
    :param start_date: תאריך תחילת עבודה (לא נדרש לחישוב הצמדה)
    :param end_work_date: תאריך סיום עבודה
    :param elig_date: תאריך הזכאות (אם None ישתמש בתאריך נוכחי)
    :return: סכום מוצמד
    """
    return calculate_adjusted_amount(amount, end_work_date, elig_date)

# ========== 2. יחס החלקיות של 32 השנים האחרונות ==========

def work_ratio_within_last_32y(start_date: Union[str, date], end_date: Union[str, date], elig_date: Union[str, date]) -> float:
    """
    מחשב את היחס של ימי העבודה בין start_date ל-end_date שנופלים
    בתוך 32 השנים שקדמו ל-elig_date.
    
    :param start_date: תאריך תחילת עבודה
    :param end_date: תאריך סיום עבודה
    :param elig_date: תאריך זכאות
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
            
        # חישוב חלון 32 השנים
        limit_start = elig_date - timedelta(days=int(365.25 * 32))
        
        # חישוב ימי עבודה כוללים
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return 0.0
            
        # חישוב חפיפה עם חלון 32 השנים
        overlap_start = max(start_date, limit_start)
        overlap_end = min(end_date, elig_date)
        overlap_days = max((overlap_end - overlap_start).days, 0)
        
        # חישוב יחס
        ratio = overlap_days / total_days if total_days > 0 else 0
        
        # גבולות [0, 1]
        ratio = min(max(ratio, 0), 1)
        
        logger.info(f"[יחסי מענק] תאריך ייחוס={elig_date}, התחלה={start_date}, "
                   f"סיום={end_date}, חפיפה={overlap_days} ימים, יחס={ratio:.4f}")
        
        return ratio
        
    except Exception as e:
        logger.error(f"[שגיאה ביחס מענק] התחלה={start_date}, סיום={end_date}, שגיאה: {str(e)}")
        return 0.0

def ratio_last_32y(start_date: Union[str, date], end_date: Union[str, date], eligibility_date: Union[str, date]) -> float:
    """
    פונקציה לתאימות לאחור - מאצילה ל-work_ratio_within_last_32y
    """
    return work_ratio_within_last_32y(start_date, end_date, eligibility_date)

# ========== 3. תקרות והון פטור ==========

# מיפוי שנה → תקרה שנתית פיצויים
ANNUAL_CAPS = {
    2025: 9430,
    2024: 9430,
    2023: 9120,
    2022: 8660,
    2021: 8460,
    2020: 8510,
    2019: 8480,
    2018: 8380,
    2017: 8360,
    2016: 8380,
    2015: 8460,
    2014: 8470,
    2013: 8310,
    2012: 8190
}

# מיפוי שנה → אחוז פטור
EXEMPTION_PERCENTAGES = {
    2025: 0.57,  # 57%
    2024: 0.52,  # 52%
    2023: 0.52,
    2022: 0.52,
    2021: 0.52,
    2020: 0.52,
    2019: 0.49,  # 49%
    2018: 0.49,
    2017: 0.49,
    2016: 0.49,
    2015: 0.435, # 43.5%
    2014: 0.435,
    2013: 0.435,
    2012: 0.435
}

# קבועים לחישוב תקרת ההון הפטורה
MULTIPLIER = 180

def get_monthly_cap(year: int) -> float:
    """החזר תקרה שנתית פיצויים; ברירת-מחדל: 2025."""
    return ANNUAL_CAPS.get(year, ANNUAL_CAPS[2025])

def get_exemption_percentage(year: int) -> float:
    """החזר את אחוז הפטור לפי שנת הזכאות"""
    return EXEMPTION_PERCENTAGES.get(year, EXEMPTION_PERCENTAGES[2025])

def calc_exempt_capital(year: int) -> float:
    """
    מחזיר תקרת הון פטורה לפי שנת הזכאות
    חישוב: תקרה שנתית פיצויים × 180 × אחוז פטור
    """
    return get_monthly_cap(year) * MULTIPLIER * get_exemption_percentage(year)

# ========== 4. חישוב פגיעה בהון הפטור ==========

def compute_grant_effect(grant: Dict[str, Any], eligibility_date: Union[str, date]) -> Optional[Dict[str, Any]]:
    """
    מחשב את השפעת המענק על ההון הפטור
    
    :param grant: מילון עם נתוני המענק (grant_amount, work_start_date, work_end_date)
    :param eligibility_date: תאריך זכאות
    :return: מילון עם תוצאות החישוב
    """
    try:
        # הצמדת המענק לסכום עדכני
        indexed_full = index_grant(
            amount=grant['grant_amount'],
            start_date=grant['work_start_date'],
            end_work_date=grant['work_end_date'],
            elig_date=eligibility_date
        )
        
        if indexed_full is None:
            logger.error(f"כשל בהצמדת מענק: {grant}")
            return None
            
        # חישוב יחס 32 השנים
        ratio = work_ratio_within_last_32y(
            start_date=grant['work_start_date'],
            end_date=grant['work_end_date'],
            elig_date=eligibility_date
        )
        
        # חישוב סכום מוגבל ל-32 שנים
        limited_indexed_amount = round(indexed_full * ratio, 2)
        
        # חישוב פגיעה בהון הפטור (הכפלה ב-1.35)
        impact_on_exemption = round(limited_indexed_amount * 1.35, 2)
        
        return {
            'indexed_full': indexed_full,
            'ratio_32y': ratio,
            'limited_indexed_amount': limited_indexed_amount,
            'impact_on_exemption': impact_on_exemption
        }
        
    except Exception as e:
        logger.error(f"שגיאה בחישוב השפעת מענק: {e}")
        return None

def compute_client_exemption(grants: List[Dict[str, Any]], eligibility_year: int) -> Dict[str, Any]:
    """
    מחשב את סך ההשפעה על ההון הפטור עבור כל המענקים של הלקוח
    
    :param grants: רשימת מענקים עם השפעות מחושבות
    :param eligibility_year: שנת זכאות
    :return: מילון עם סיכום ההשפעות
    """
    try:
        # חישוב תקרת ההון הפטורה ההתחלתית
        exempt_capital_initial = calc_exempt_capital(eligibility_year)
        
        # סיכום השפעות כל המענקים
        total_impact = sum(grant.get('impact_on_exemption', 0) for grant in grants)
        
        # חישוב הון פטור נותר
        remaining_exempt_capital = max(exempt_capital_initial - total_impact, 0)
        
        # חישוב פטור חודשי נותר
        exemption_percentage = get_exemption_percentage(eligibility_year)
        remaining_monthly_exemption = round(remaining_exempt_capital / (180 * exemption_percentage), 2) if exemption_percentage > 0 else 0
        
        return {
            'exempt_capital_initial': exempt_capital_initial,
            'total_impact': total_impact,
            'remaining_exempt_capital': remaining_exempt_capital,
            'remaining_monthly_exemption': remaining_monthly_exemption,
            'eligibility_year': eligibility_year,
            'exemption_percentage': exemption_percentage
        }
        
    except Exception as e:
        logger.error(f"שגיאה בחישוב פטור לקוח: {e}")
        return {
            'exempt_capital_initial': 0,
            'total_impact': 0,
            'remaining_exempt_capital': 0,
            'remaining_monthly_exemption': 0,
            'eligibility_year': eligibility_year,
            'exemption_percentage': 0
        }

# ========== 5. זכאות גיל ==========

def calculate_eligibility_age(birth_date: date, gender: str, pension_start: date) -> date:
    """
    חישוב תאריך זכאות על בסיס גיל, מגדר ותאריך תחילת קצבה
    
    :param birth_date: תאריך לידה
    :param gender: מגדר ('male' או 'female')
    :param pension_start: תאריך תחילת קצבה מבוקש
    :return: תאריך זכאות (המקסימום בין גיל זכאות חוקי לתאריך תחילת קצבה)
    """
    # גיל פרישה לפי מגדר
    legal_retirement_age = date(
        birth_date.year + (67 if gender == "male" else 62), 
        birth_date.month, 
        birth_date.day
    )
    return max(legal_retirement_age, pension_start)

# ========== 6. פונקציות שירות מרכזיות ==========

def process_grant(grant: Dict[str, Any], eligibility_date: Union[str, date]) -> Dict[str, Any]:
    """
    מעבד מענק בודד - מחשב הצמדה, יחס ופגיעה
    
    :param grant: נתוני המענק
    :param eligibility_date: תאריך זכאות
    :return: מענק מעודכן עם חישובים
    """
    effect = compute_grant_effect(grant, eligibility_date)
    if effect:
        grant.update(effect)
    return grant

def calculate_full_fixation(client_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    מחשב קיבוע זכויות מלא עבור לקוח
    
    :param client_data: נתוני הלקוח כולל מענקים ותאריך זכאות
    :return: תוצאות קיבוע זכויות מלאות
    """
    try:
        grants = client_data.get('grants', [])
        eligibility_date = client_data.get('eligibility_date')
        eligibility_year = client_data.get('eligibility_year', 2025)
        
        if not eligibility_date:
            raise ValueError("חסר תאריך זכאות")
            
        # עיבוד כל המענקים
        processed_grants = []
        for grant in grants:
            processed_grant = process_grant(grant, eligibility_date)
            processed_grants.append(processed_grant)
        
        # חישוב סיכום הפטור
        exemption_summary = compute_client_exemption(processed_grants, eligibility_year)
        
        return {
            'grants': processed_grants,
            'exemption_summary': exemption_summary,
            'eligibility_date': eligibility_date,
            'eligibility_year': eligibility_year
        }
        
    except Exception as e:
        logger.error(f"שגיאה בחישוב קיבוע זכויות: {e}")
        return {
            'grants': [],
            'exemption_summary': {},
            'error': str(e)
        }
