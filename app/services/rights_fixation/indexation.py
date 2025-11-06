"""
מודול הצמדה למדד - חישובי הצמדה באמצעות API של הלמ"ס
"""
import requests
from datetime import datetime, date
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

# CBS Consumer Price Index API endpoint
CBS_CPI_API = "https://api.cbs.gov.il/index/data/calculator/120010"


def calculate_adjusted_amount(
    amount: float, 
    grant_date: Union[str, date], 
    to_date: Optional[Union[str, date]] = None
) -> Optional[float]:
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


def index_grant(
    amount: float, 
    start_date: Union[str, date], 
    grant_date: Union[str, date], 
    elig_date: Optional[Union[str, date]] = None
) -> Optional[float]:
    """
    פונקציה עוטפת להצמדת מענק
    
    :param amount: סכום נומינלי
    :param start_date: תאריך תחילת עבודה (לא נדרש לחישוב הצמדה)
    :param grant_date: תאריך המענק
    :param elig_date: תאריך הזכאות (אם None ישתמש בתאריך נוכחי)
    :return: סכום מוצמד
    """
    return calculate_adjusted_amount(amount, grant_date, elig_date)
