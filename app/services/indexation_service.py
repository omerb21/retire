"""
שירות הצמדה מתקדם המבוסס על מערכת קיבוע הזכויות הקיימת
"""
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# CBS Consumer Price Index API endpoint
CBS_CPI_API = 'https://api.cbs.gov.il/index/data/calculator/120010'

class IndexationService:
    """שירות הצמדה מתקדם"""
    
    @staticmethod
    def calculate_adjusted_amount(amount: float, end_work_date: str, to_date: Optional[str] = None) -> Optional[float]:
        """
        מחשב את הסכום המוצמד לפי API של הלמ"ס
        
        :param amount: סכום נומינלי להצמדה
        :param end_work_date: תאריך סיום עבודה (YYYY-MM-DD)
        :param to_date: תאריך יעד להצמדה (אם None, ישתמש בתאריך נוכחי)
        :return: סכום מוצמד או None בשגיאה
        """
        try:
            # וידוא שהתאריך היעד מועבר כמחרוזת בפורמט YYYY-MM-DD
            if to_date and not isinstance(to_date, str):
                to_date = to_date.isoformat()
                
            params = {
                'value': amount, 
                'date': end_work_date,
                'toDate': to_date if to_date else datetime.today().date().isoformat(), 
                'format': 'json', 
                'download': 'false'
            }
            
            resp = requests.get(CBS_CPI_API, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
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

    @staticmethod
    def index_grant(amount: float, start_date: str, end_work_date: str, 
                   elig_date: Optional[str] = None) -> Optional[float]:
        """
        פונקציה עוטפת שמשתמשת בפונקציה הנכונה calculate_adjusted_amount
        
        :param amount: סכום נומינלי
        :param start_date: תאריך תחילת עבודה (לא נדרש לחישוב הצמדה)
        :param end_work_date: תאריך סיום עבודה
        :param elig_date: תאריך הזכאות (אם None ישתמש בתאריך נוכחי)
        :return: סכום מוצמד
        """
        if elig_date:
            # אם יש תאריך זכאות, נצטרך להמיר את התאריך לאובייקט מתאים
            elig_date_obj = date.fromisoformat(elig_date)
            return IndexationService.calculate_adjusted_amount(amount, end_work_date, elig_date_obj)
        else:
            # ללא תאריך זכאות - נשתמש בתאריך נוכחי
            return IndexationService.calculate_adjusted_amount(amount, end_work_date)

    @staticmethod
    def work_ratio_within_last_32y(start_date: str, end_date: str, elig_date: str, birth_date: Optional[date] = None, gender: Optional[str] = None) -> float:
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
                
            today = elig_date  # השתמש תמיד בתאריך הזכאות
            limit_start = today - timedelta(days=int(365.25 * 32))
            
            # חישוב ימי עבודה כוללים (עד גיל פרישה)
            total_days = (effective_end_date - start_date).days
            if total_days <= 0:
                logger.info(f"[יחסי מענק] אין ימי עבודה רלוונטיים (עבודה לאחר גיל פרישה)")
                return 0.0
                
            overlap_start = max(start_date, limit_start)
            overlap_end = min(effective_end_date, today)
            overlap_days = max((overlap_end - overlap_start).days, 0)
            
            ratio = (overlap_days / total_days) if total_days > 0 else 0
            # גבולות
            ratio = min(max(ratio, 0), 1)
            
            logger.info(f"[יחסי מענק] תאריך ייחוס={today}, התחלה={start_date}, "
                       f"סיום מקורי={end_date}, סיום אפקטיבי={effective_end_date}, "
                       f"חפיפה={overlap_days} ימים, יחס={ratio:.4f}")
            return ratio
            
        except Exception as e:
            logger.error(f"[שגיאה ביחס מענק] התחלה={start_date}, סיום={end_date}, שגיאה: {str(e)}")
            return 0.0

    @staticmethod
    def calculate_eligibility_age(birth_date: date, gender: str, pension_start_date: date) -> date:
        """
        חישוב תאריך זכאות לפי גיל פרישה
        """
        # גיל פרישה בישראל: גברים 67, נשים 62
        retirement_age = 67 if gender.lower() in ['m', 'male', 'זכר'] else 62
        
        # חישוב תאריך זכאות
        eligibility_date = date(birth_date.year + retirement_age, birth_date.month, birth_date.day)
        
        # אם תאריך הפנסיה מאוחר יותר, נשתמש בו
        return max(eligibility_date, pension_start_date)

    @staticmethod
    def calculate_exact_grant_value(grant_data: Dict[str, Any], eligibility_date: Optional[str] = None) -> Dict[str, Any]:
        """
        חישוב מדויק של ערך מענק כולל הצמדה ויחסים
        
        :param grant_data: נתוני המענק (grant_amount, work_start_date, work_end_date)
        :param eligibility_date: תאריך זכאות (אם None ישתמש בתאריך נוכחי)
        :return: תוצאות החישוב המפורטות
        """
        try:
            amount = grant_data.get('grant_amount', 0)
            start_date = grant_data.get('work_start_date')
            end_date = grant_data.get('work_end_date')
            
            if not all([amount, start_date, end_date]):
                return {
                    'error': 'חסרים נתונים חיוניים לחישוב',
                    'nominal_amount': amount,
                    'indexed_amount': amount,
                    'ratio': 1.0,
                    'final_amount': amount,
                    'impact_on_exemption': amount * 1.35
                }
            
            # הצמדה מלאה
            indexed_full = IndexationService.index_grant(
                amount=amount,
                start_date=start_date,
                end_work_date=end_date,
                elig_date=eligibility_date
            )
            
            if indexed_full is None:
                indexed_full = amount  # fallback
            
            # חישוב יחס 32 שנה
            if eligibility_date:
                ratio = IndexationService.work_ratio_within_last_32y(
                    start_date, end_date, eligibility_date
                )
            else:
                ratio = 1.0  # אם אין תאריך זכאות, נשתמש ביחס מלא
            
            # חישוב הסכום הסופי
            final_indexed_amount = indexed_full * ratio
            impact_on_exemption = final_indexed_amount * 1.35
            
            return {
                'nominal_amount': amount,
                'indexed_full': indexed_full,
                'ratio': ratio,
                'indexed_amount': final_indexed_amount,
                'impact_on_exemption': impact_on_exemption,
                'calculation_details': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'eligibility_date': eligibility_date or datetime.today().date().isoformat(),
                    'indexation_factor': indexed_full / amount if amount > 0 else 1.0
                }
            }
            
        except Exception as e:
            logger.error(f'שגיאה בחישוב מדויק של מענק: {e}')
            return {
                'error': str(e),
                'nominal_amount': grant_data.get('grant_amount', 0),
                'indexed_amount': grant_data.get('grant_amount', 0),
                'ratio': 1.0,
                'final_amount': grant_data.get('grant_amount', 0),
                'impact_on_exemption': grant_data.get('grant_amount', 0) * 1.35
            }
