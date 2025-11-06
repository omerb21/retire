"""
מודול חישוב פגיעה בהון הפטור - חישוב השפעת מענקים על ההון הפטור
"""
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Union
import logging

from .indexation import calculate_adjusted_amount
from .work_ratio import work_ratio_within_last_32y
from .exemption_caps import calc_exempt_capital, get_monthly_cap, get_exemption_percentage

logger = logging.getLogger(__name__)


def compute_grant_effect(
    grant: Dict[str, Any], 
    eligibility_date: Union[str, date], 
    birth_date: Optional[Union[str, date]] = None, 
    gender: Optional[str] = None
) -> Optional[Dict[str, Any]]:
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
        
        # חישוב אחוז הפטור המחושב של הלקוח (לפני קיזוז)
        # האחוז המחושב = יתרה נותרת / יתרה התחלתית
        calculated_exemption_percentage = (remaining_exempt_capital / exempt_capital_initial) if exempt_capital_initial > 0 else 0
        
        # חישוב אחוז קצבה פטורה מחושבת (אחרי קיזוז)
        # אחוז קצבה פטורה = (יתרה נותרת / 180) / תקרת קצבה של שנת הזכאות
        pension_ceiling = get_monthly_cap(eligibility_year)
        calculated_pension_exemption_percentage = ((remaining_exempt_capital / 180) / pension_ceiling) if pension_ceiling > 0 else 0
        
        # חישוב פטור חודשי נותר (לפי אחוז הקצבה הפטורה המחושבת)
        general_exemption_percentage = get_exemption_percentage(eligibility_year)
        remaining_monthly_exemption = round(calculated_pension_exemption_percentage * pension_ceiling, 2)
        
        return {
            'exempt_capital_initial': exempt_capital_initial,
            'total_impact': total_impact,
            'remaining_exempt_capital': remaining_exempt_capital,
            'remaining_monthly_exemption': remaining_monthly_exemption,
            'eligibility_year': eligibility_year,
            'exemption_percentage': calculated_exemption_percentage,  # האחוז המחושב של הלקוח (לפני קיזוז)
            'calculated_pension_exemption_percentage': calculated_pension_exemption_percentage,  # אחוז קצבה פטורה מחושבת (אחרי קיזוז)
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
