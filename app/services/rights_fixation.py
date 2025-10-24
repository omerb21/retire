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

def calculate_adjusted_amount(amount: float, grant_date: Union[str, date], to_date: Optional[Union[str, date]] = None) -> Optional[float]:
    """
    מחשב את הסכום המוצמד לפי API של הלמ"ס
    
    :param amount: סכום נומינלי להצמדה
    :param grant_date: תאריך המענק (YYYY-MM-DD)
    :param to_date: תאריך יעד להצמדה (אם None, ישתמש בתאריך נוכחי)
    :return: סכום מוצמד או None בשגיאה
    """
    try:
        # וידוא שהתאריכים מועברים כמחרוזות בפורמט YYYY-MM-DD
        if isinstance(grant_date, date):
            grant_date_str = grant_date.isoformat()
        else:
            grant_date_str = str(grant_date)
            
        if to_date and isinstance(to_date, date):
            to_date_str = to_date.isoformat()
        else:
            to_date_str = str(to_date) if to_date else datetime.today().date().isoformat()
        
        logger.info(f"Calculating indexation from {grant_date_str} to {to_date_str}")
            
        # בדיקה אם התאריכים תקינים
        try:
            from_date = datetime.strptime(grant_date_str, '%Y-%m-%d').date()
            to_date_parsed = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            
            if from_date > to_date_parsed:
                logger.warning(f"תאריך התחלה {grant_date_str} מאוחר מתאריך סיום {to_date_str}")
                return float(amount)  # מחזירים את הסכום המקורי בלי הצמדה
                
        except ValueError as e:
            logger.error(f"שגיאה בניתוח תאריכים: {e}")
            return None
            
        params = {
            'value': amount, 
            'date': grant_date_str,  # תאריך המענק
            'toDate': to_date_str,  # תאריך יעד להצמדה
            'format': 'json', 
            'download': 'false',
            'lang': 'he'  # לוודא שהתוצאות בעברית
        }
        
        logger.info(f"Calling CBS API with params: {params}")
        response = requests.get(CBS_CPI_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"Raw API response: {data}")
        
        answer = data.get('answer')
        if not answer:
            logger.warning(f'אזהרה: API ללא answer | תשובה: {data}')
            return None
            
        to_value = answer.get('to_value')
        if to_value is None:
            logger.warning(f'אזהרה: אין to_value | תשובה: {data}')
            return None
        
        result = round(float(to_value), 2)
        logger.info(f"Calculated adjusted amount: {amount} from {grant_date_str} to {to_date_str} = {result}")
        return result
        
    except Exception as e:
        # שימוש במשתני ברירת מחדל במקרה של שגיאה
        error_grant_date = grant_date.isoformat() if isinstance(grant_date, date) else str(grant_date)
        error_to_date = to_date.isoformat() if to_date and isinstance(to_date, date) else (str(to_date) if to_date else 'now')
        logger.error(f'שגיאה בהצמדה מתאריך {error_grant_date} לתאריך {error_to_date}: {e}', exc_info=True)
        return None

def index_grant(amount: float, start_date: Union[str, date], grant_date: Union[str, date], elig_date: Optional[Union[str, date]] = None) -> Optional[float]:
    """
    פונקציה עוטפת להצמדת מענק
    
    :param amount: סכום נומינלי
    :param start_date: תאריך תחילת עבודה (לא נדרש לחישוב הצמדה)
    :param grant_date: תאריך המענק
    :param elig_date: תאריך הזכאות (אם None ישתמש בתאריך נוכחי)
    :return: סכום מוצמד
    """
    return calculate_adjusted_amount(amount, grant_date, elig_date)

# ========== 2. יחס החלקיות של 32 השנים האחרונות ==========

def work_ratio_within_last_32y(start_date: Union[str, date], end_date: Union[str, date], elig_date: Union[str, date], birth_date: Optional[Union[str, date]] = None, gender: Optional[str] = None) -> float:
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
        
        # חישוב ימי עבודה כוללים (עד גיל פרישה)
        total_days = (effective_end_date - start_date).days
        if total_days <= 0:
            logger.info(f"[יחסי מענק] אין ימי עבודה רלוונטיים (עבודה לאחר גיל פרישה)")
            return 0.0
            
        # חישוב חפיפה עם חלון 32 השנים (מוגבל לגיל פרישה)
        overlap_start = max(start_date, limit_start)
        overlap_end = min(effective_end_date, elig_date)
        overlap_days = max((overlap_end - overlap_start).days, 0)
        
        # חישוב יחס
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

def ratio_last_32y(start_date: Union[str, date], end_date: Union[str, date], eligibility_date: Union[str, date]) -> float:
    """
    פונקציה לתאימות לאחור - מאצילה ל-work_ratio_within_last_32y
    """
    return work_ratio_within_last_32y(start_date, end_date, eligibility_date)

# ========== 3. תקרות והון פטור ==========

# מיפוי שנה → תקרה שנתית פיצויים
ANNUAL_CAPS = {
    2028: 9430,  # ברירת מחדל לשנים עתידיות
    2027: 9430,
    2026: 9430,
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
# 2012-2015: 43.5%
# 2016-2019: 49%
# 2020-2024: 52%
# 2025: 57%
# 2026: 57.5%
# 2027: 62.5%
# 2028+: 67%
EXEMPTION_PERCENTAGES = {
    2028: 0.67,  # 67% - החל משנת 2028 ואילך
    2027: 0.625, # 62.5%
    2026: 0.575, # 57.5%
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
    """החזר תקרה שנתית פיצויים; ברירת-מחדל: 9430 לשנים עתידיות."""
    if year >= 2028:
        return ANNUAL_CAPS.get(2028, 9430)
    return ANNUAL_CAPS.get(year, ANNUAL_CAPS[2025])

def get_exemption_percentage(year: int) -> float:
    """החזר את אחוז הפטור לפי שנת הזכאות; ברירת-מחדל: 67% לשנת 2028 ואילך."""
    if year >= 2028:
        return EXEMPTION_PERCENTAGES.get(2028, 0.67)
    return EXEMPTION_PERCENTAGES.get(year, EXEMPTION_PERCENTAGES[2025])

def calc_exempt_capital(year: int) -> float:
    """
    מחזיר תקרת הון פטורה לפי שנת הזכאות
    חישוב: תקרה שנתית פיצויים × 180 × אחוז פטור
    """
    return get_monthly_cap(year) * MULTIPLIER * get_exemption_percentage(year)

# ========== 4. חישוב פגיעה בהון הפטור ==========

def compute_grant_effect(grant: Dict[str, Any], eligibility_date: Union[str, date], birth_date: Optional[Union[str, date]] = None, gender: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    מחשב את השפעת המענק על ההון הפטור
    
    :param grant: מילון עם נתוני המענק (grant_amount, work_start_date, work_end_date)
    :param eligibility_date: תאריך זכאות
    :param birth_date: תאריך לידה (אופציונלי - לחישוב גיל פרישה)
    :param gender: מגדר (אופציונלי - לחישוב גיל פרישה)
    :return: מילון עם תוצאות החישוב
    """
    try:
        # הצמדת המענק לסכום עדכני - מתאריך קבלת המענק
        grant_date = grant.get('grant_date', grant['work_end_date'])  # fallback לתאריך סיום עבודה אם אין grant_date
        logger.info(f"DEBUG: Using grant_date={grant_date} for indexation")
        
        # קריאה לפונקציה עם הפרמטרים המעודכנים
        indexed_full = calculate_adjusted_amount(
            amount=grant['grant_amount'],
            grant_date=grant_date,  # שימוש ב-grant_date במקום end_work_date
            to_date=eligibility_date
        )
        logger.info(f"DEBUG: Indexed amount result: {indexed_full}")
        
        if indexed_full is None:
            logger.error(f"כשל בהצמדת מענק: {grant}")
            return None
            
        # חישוב יחס 32 השנים עם הגבלה לפי גיל פרישה
        ratio = work_ratio_within_last_32y(
            start_date=grant['work_start_date'],
            end_date=grant['work_end_date'],
            elig_date=eligibility_date,
            birth_date=birth_date,
            gender=gender
        )
        
        # חישוב סכום מוגבל ל-32 שנים
        limited_indexed_amount = round(indexed_full * ratio, 2)
        
        # בדיקת חוק "15 השנים" - ביטול קיזוז בגין היוון קצבה מוקדם
        # אם חלפו יותר מ-15 שנים בין תאריך המענק לתאריך הזכאות, לא נחשב את ההשפעה על ההון הפטור
        
        # המרת תאריכים לאובייקטי date אם הם מחרוזות
        if isinstance(grant_date, str):
            grant_date_obj = datetime.strptime(grant_date, '%Y-%m-%d').date()
        else:
            grant_date_obj = grant_date
            
        if isinstance(eligibility_date, str):
            eligibility_date_obj = datetime.strptime(eligibility_date, '%Y-%m-%d').date()
        else:
            eligibility_date_obj = eligibility_date
        
        # חישוב הפרש השנים
        years_diff = (eligibility_date_obj.year - grant_date_obj.year) + \
                     (eligibility_date_obj.month - grant_date_obj.month) / 12 + \
                     (eligibility_date_obj.day - grant_date_obj.day) / 365.25
        
        # בדיקה אם חלפו יותר מ-15 שנים
        exclusion_reason = None
        if years_diff > 15:
            logger.info(f"DEBUG: חוק 15 השנים חל - חלפו {years_diff:.2f} שנים בין המענק לזכאות")
            impact_on_exemption = 0  # אין השפעה על ההון הפטור
            exclusion_reason = "חוק 15 השנים - מענק ישן"
        else:
            # חישוב פגיעה בהון הפטור (הכפלה ב-1.35)
            impact_on_exemption = round(limited_indexed_amount * 1.35, 2)
            logger.info(f"DEBUG: חוק 15 השנים לא חל - חלפו {years_diff:.2f} שנים בין המענק לזכאות")
        
        result = {
            'indexed_full': indexed_full,
            'ratio_32y': ratio,
            'limited_indexed_amount': limited_indexed_amount,
            'impact_on_exemption': impact_on_exemption
        }
        
        # הוספת סיבת החרגה אם קיימת
        if exclusion_reason:
            result['exclusion_reason'] = exclusion_reason
            
        return result
        
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
        
        # חישוב אחוז הפטור המחושב של הלקוח
        # האחוז המחושב = יתרה נותרת / יתרה התחלתית
        calculated_exemption_percentage = (remaining_exempt_capital / exempt_capital_initial) if exempt_capital_initial > 0 else 0
        
        # חישוב פטור חודשי נותר (לפי האחוז הכללי של השנה)
        general_exemption_percentage = get_exemption_percentage(eligibility_year)
        remaining_monthly_exemption = round(remaining_exempt_capital / 180, 2)
        
        return {
            'exempt_capital_initial': exempt_capital_initial,
            'total_impact': total_impact,
            'remaining_exempt_capital': remaining_exempt_capital,
            'remaining_monthly_exemption': remaining_monthly_exemption,
            'eligibility_year': eligibility_year,
            'exemption_percentage': calculated_exemption_percentage,  # האחוז המחושב של הלקוח
            'general_exemption_percentage': general_exemption_percentage  # האחוז הכללי של השנה
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

def process_grant(grant: Dict[str, Any], eligibility_date: Union[str, date], birth_date: Optional[Union[str, date]] = None, gender: Optional[str] = None) -> Dict[str, Any]:
    """
    מעבד מענק בודד - מחשב הצמדה, יחס ופגיעה
    
    :param grant: נתוני המענק
    :param eligibility_date: תאריך זכאות
    :param birth_date: תאריך לידה (אופציונלי)
    :param gender: מגדר (אופציונלי)
    :return: מענק מעודכן עם חישובים
    """
    effect = compute_grant_effect(grant, eligibility_date, birth_date, gender)
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
        birth_date = client_data.get('birth_date')  # תאריך לידה לחישוב גיל פרישה
        gender = client_data.get('gender')  # מגדר לחישוב גיל פרישה
        
        if not eligibility_date:
            raise ValueError("חסר תאריך זכאות")
            
        # עיבוד כל המענקים עם נתוני לקוח
        processed_grants = []
        for grant in grants:
            processed_grant = process_grant(grant, eligibility_date, birth_date, gender)
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
