"""
מודול ליבה - פונקציות שירות מרכזיות לקיבוע זכויות
"""
from typing import Dict, Any, Optional, Union
from datetime import date
import logging

from .grant_impact import compute_grant_effect, compute_client_exemption

logger = logging.getLogger(__name__)


def process_grant(
    grant: Dict[str, Any], 
    eligibility_date: Union[str, date], 
    birth_date: Optional[Union[str, date]] = None, 
    gender: Optional[str] = None
) -> Dict[str, Any]:
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
